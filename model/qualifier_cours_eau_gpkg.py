"""Install persistent hydro qualification using only SQLite core BLOB operations.

Only standard GeoPackage LineString/MultiLineString (ISO WKB, XY/Z/M) are
accepted. No spatial extension is required by the qualification triggers.
Existing RTree triggers still require the spatial functions supplied by QGIS/GDAL.
"""
import argparse
import json
import re
import sqlite3
import struct
from pathlib import Path


def wkb(blob):
    if blob is None:
        return None
    if blob[:2] != b'GP':
        raise ValueError('Géométrie non GeoPackage')
    return blob[8 + (0, 32, 48, 48, 64)[(blob[3] >> 1) & 7]:]


def parts(blob):
    data = wkb(blob)
    if data is None:
        return None
    endian = '<' if data[0] == 1 else '>'
    kind = struct.unpack(endian + 'I', data[1:5])[0] % 1000
    if kind == 2:
        return 1
    if kind == 5:
        return struct.unpack(endian + 'I', data[5:9])[0]
    raise ValueError('Seuls LineString et MultiLineString sont acceptés')


def byte(expr, position):
    h = f'hex(substr({expr},{position},1))'
    return f'((instr(\'0123456789ABCDEF\',substr({h},1,1))-1)*16+instr(\'0123456789ABCDEF\',substr({h},2,1))-1)'


def payload(expr):
    offset = f'(9+CASE (({byte(expr,4)} >> 1) & 7) WHEN 0 THEN 0 WHEN 1 THEN 32 WHEN 2 THEN 48 WHEN 3 THEN 48 WHEN 4 THEN 64 END)'
    return f'substr({expr},{offset})'


def uint(expr, start):
    little = '+'.join(f'{byte(expr,start+i)}*{256**i}' for i in range(4))
    big = '+'.join(f'{byte(expr,start+i)}*{256**(3-i)}' for i in range(4))
    return f'(CASE hex(substr({expr},1,1)) WHEN \'01\' THEN {little} ELSE {big} END)'


def section_sql(expr):
    data = payload(expr)
    return f'(CASE WHEN {expr} IS NULL THEN NULL WHEN ({uint(data,2)} % 1000)=2 THEN 1 WHEN ({uint(data,2)} % 1000)=5 THEN {uint(data,6)} ELSE NULL END)'


def install(path, backup):
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        raise ValueError('La sauvegarde existe déjà : choisir un nouveau chemin')
    with sqlite3.connect(path) as db:
        with sqlite3.connect(backup) as target:
            db.backup(target)
        db.execute('BEGIN IMMEDIATE')
        columns = db.execute('PRAGMA table_info(cours_eau)').fetchall()
        names = [c[1] for c in columns]
        rows = db.execute('SELECT * FROM cours_eau ORDER BY fid').fetchall()
        old_schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cours_eau'").fetchone()[0]
        objects = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='cours_eau' AND type IN ('trigger','index') AND sql IS NOT NULL AND name NOT LIKE 'hydro_qual_%'").fetchall()
        result = []
        new_names = ['section' if n == 'sections' else n for n in names]
        if 'direction' not in names:
            new_names.append('direction')
            old_schema = old_schema[:-1] + ', direction BOOLEAN)'
        if 'section' not in new_names:
            new_names.append('section')
            old_schema = old_schema[:-1] + ', section INTEGER)'
        old_schema = re.sub(r'\bsections\b', 'section', old_schema)
        old_schema = re.sub(r'("?valide"?\s+BOOLEAN)(?:\s+NOT NULL(?:\s+ON CONFLICT REPLACE)?)?(?:\s+DEFAULT\s+0)?', r'\1 NOT NULL ON CONFLICT REPLACE DEFAULT 0', old_schema, flags=re.I)
        old_schema = re.sub(r'("?section"?\s+)MEDIUMINT', r'\1INTEGER', old_schema, flags=re.I)
        for row in rows:
            obj = dict(zip(names, row))
            direction = obj.get('direction')
            if direction not in (None, 0, 1):
                raise ValueError('Direction hors domaine')
            obj['direction'] = direction
            obj['section'] = parts(obj['geom'])
            obj['valide'] = int(direction == 1 and obj['section'] == 1)
            result.append(tuple(obj.get(n) for n in new_names))
        db.execute('DROP TABLE cours_eau')
        db.execute(old_schema)
        fields = ','.join('"'+n+'"' for n in new_names)
        db.executemany(f'INSERT INTO cours_eau ({fields}) VALUES ({",".join("?" for _ in new_names)})', result)
        for sql, in objects:
            db.execute(sql)
        section = section_sql('NEW.geom')
        changed = f'({payload("NEW.geom")} IS NOT {payload("OLD.geom")} OR substr(NEW.geom,5,4) IS NOT substr(OLD.geom,5,4))'
        # One update trigger computes all three values; its own update converges
        # even with recursive_triggers enabled. An unchanged WKB keeps direction.
        for event in ('INSERT', 'UPDATE'):
            direction = f'CASE WHEN {changed} THEN NULL ELSE NEW.direction END' if event == 'UPDATE' else 'NEW.direction'
            valid = f'COALESCE((({direction}) IS 1 AND {section}=1),0)'
            condition = f'NEW.section IS NOT {section} OR NEW.valide IS NOT {valid}'
            if event == 'UPDATE':
                condition += f' OR ({changed} AND NEW.direction IS NOT NULL)'
            db.execute(f'CREATE TRIGGER hydro_qual_{event.lower()} AFTER {event} ON cours_eau WHEN {condition} BEGIN UPDATE cours_eau SET direction={direction},section={section},valide={valid} WHERE fid=NEW.fid; END')
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        print(json.dumps({'file': str(path), 'count': len(rows), 'before': db_summary(backup), 'after': db.execute('SELECT direction,section,valide,count(*) FROM cours_eau GROUP BY 1,2,3').fetchall()}, ensure_ascii=False))


def db_summary(path):
    with sqlite3.connect(path) as db:
        return db.execute('SELECT valide,count(*) FROM cours_eau GROUP BY valide').fetchall()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('gpkg', type=Path)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    install(args.gpkg, args.backup)
