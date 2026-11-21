"""Bounded isolated PyQGIS stress processes, with simulated network and local audio.

Run with /usr/bin/python3 plugin/tests/test_voice_stability.py. No paid API or DB.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def child(scenario):
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    import copy
    import time
    from unittest.mock import Mock, patch
    from qgis.PyQt import sip
    from qgis.PyQt.QtCore import QCoreApplication, QEvent, QObject, QSettings
    from qgis.PyQt.QtTest import QTest
    from qgis.PyQt.QtMultimedia import QAudioDeviceInfo, QAudioInput, QAudioOutput
    from qgis.core import QgsApplication
    sys.path.insert(0, str(ROOT / 'plugin'))
    import test_voice as fixtures
    from gemapi_app.voice import Recorder, Speaker, _CAPTURES, _PLAYBACKS, parse_speech
    from gemapi_app.assistant_dialog import AssistantDialog
    from test_assistant import CATALOG, FULL, COMPLETE_PHRASE, response
    app = QgsApplication([], True)
    app.initQgis()
    callback_errors = []
    def callback_error(kind, error, trace):
        import traceback
        callback_errors.append(kind.__name__)
        traceback.print_exception(kind, error, trace)  # Only synthetic test inputs in this process.
    sys.excepthook = callback_error
    device = Mock()
    device.isNull.return_value = False
    device.isFormatSupported.return_value = True

    def drain(predicate, limit=150):
        for _ in range(limit):
            QTest.qWait(5)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            if predicate():
                return
        raise AssertionError('Resources did not finish before deadline')

    class SlowOutput(fixtures.FakeOutput):
        def start(self, buffer):
            time.sleep(.025)  # A slow native device must not multiply workers.
            super().start(buffer)

    native = scenario == 'native'
    input_device, output_device = QAudioDeviceInfo.defaultInputDevice, QAudioDeviceInfo.defaultOutputDevice
    with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultInputDevice',
               side_effect=input_device if native else lambda: device), patch(
            'qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice',
            side_effect=output_device if native else lambda: device), patch(
            'qgis.PyQt.QtMultimedia.QAudioInput', QAudioInput if native else fixtures.FakeAudio), patch(
            'qgis.PyQt.QtMultimedia.QAudioOutput', QAudioOutput if native else SlowOutput), patch(
            'gemapi_app.assistant_dialog.load_catalog', return_value=copy.deepcopy(CATALOG)), patch(
            'gemapi_app.assistant_dialog.read_api_key', return_value='simulated-key'):
        try:
            if native:
                parent = QObject()
                speaker, recorder = Speaker(parent), Recorder(parent)
                statuses = []
                speaker.status.connect(statuses.append)
                capture_statuses = []
                recorder.status.connect(capture_statuses.append)
                for index in range(32):
                    statuses.clear()
                    speaker.set_text('Réponse locale de test.')
                    speaker.audio = (b'\0' * 24000, 24000, 1)
                    speaker.speak(Mock(), '')
                    drain(lambda: any(s.startswith('Lecture de la réponse') for s in statuses))
                    speaker.stop(clear=True)
                    drain(lambda: not _PLAYBACKS)
                    if index % 8 == 0:
                        capture_statuses.clear()
                        recorder.start()
                        drain(lambda: any('Microphone actif' in s for s in capture_statuses))
                        recorder.cancel()
                        drain(lambda: not _CAPTURES)
                statuses.clear()
                speaker.set_text('Réponse terminée normalement.')
                speaker.audio = (b'\0' * 24000, 24000, 1)
                speaker.speak(Mock(), '')
                drain(lambda: not speaker.busy, limit=600)
                assert any('Lecture terminée' in text for text in statuses), statuses
                sip.delete(parent)
                drain(lambda: not _CAPTURES and not _PLAYBACKS)
            elif scenario == 'owners':
                for _ in range(20):
                    parent = QObject()
                    recorder, speaker = Recorder(parent), Speaker(parent)
                    recorder.start()
                    speaker.set_text('Brouillon de test.')
                    speaker.audio = parse_speech(fixtures.speech_response())
                    speaker.speak(Mock(), '')
                    QTest.qWait(10)
                    sip.delete(parent)  # QGIS can destroy a window through its parent.
                    drain(lambda: not _CAPTURES and not _PLAYBACKS)
            elif scenario == 'replacement':
                speaker = Speaker()
                for _ in range(50):
                    speaker.set_text('Réponse de test.')
                    speaker.audio = parse_speech(fixtures.speech_response())
                    speaker.speak(Mock(), '')
                    speaker.stop()
                    assert len(_PLAYBACKS) <= 1, 'Overlapping cancelled audio workers'
                drain(lambda: not _PLAYBACKS)
                speaker.deleteLater()
            else:
                for index in range(50):
                    session = fixtures.fixtures.Session()
                    dialog = AssistantDialog(session, Mock(), before_new=lambda _: True)
                    dialog.show()
                    manager = Mock()
                    dialog.network = manager
                    small = fixtures.fixtures.Reply(response(**FULL))
                    speech = fixtures.SpeechReply(fixtures.speech_response())
                    manager.post.side_effect = [small, speech]
                    dialog.speech_enabled.setChecked(True)
                    dialog.submit_user_message(COMPLETE_PHRASE)
                    if index % 4 == 0:
                        dialog.cancel_request()
                        small.complete()
                    else:
                        small.complete()
                        if scenario == 'queued':
                            dialog.close()
                            sip.delete(dialog)
                            QTest.qWait(5)  # Flush work queued by _refresh on a deleted window.
                            drain(lambda: not _PLAYBACKS and not _CAPTURES)
                            continue
                        if index % 4 == 1:
                            speech.complete()
                            dialog._stop_speech()
                        elif index % 4 == 2:
                            dialog.hide()
                            speech.complete()
                            dialog.show()
                        else:
                            dialog.new_prestation()
                            speech.complete()
                    dialog.new_prestation()
                    dialog._toggle_microphone()
                    QTest.qWait(5)
                    dialog.close()  # Close while native capture is still starting.
                    dialog.show()
                    dialog.close()
                    dialog.deleteLater()
                    drain(lambda: not _PLAYBACKS and not _CAPTURES)
                    session.db.executeSql.assert_not_called()
            print(f'{scenario}: repetitions complete; no remaining audio workers', flush=True)
        finally:
            # The test must report a controlled failure even for a broken baseline.
            for thread in list(_CAPTURES | _PLAYBACKS):
                thread.requestInterruption()
                thread.quit()
            for _ in range(100):
                QTest.qWait(5)
                if not _CAPTURES and not _PLAYBACKS:
                    break
    app.exitQgis()
    assert not callback_errors, f'Unhandled Qt callbacks: {callback_errors}'


class IsolatedStabilityTests(unittest.TestCase):
    def run_scenario(self, scenario):
        audits = ROOT / 'audits/ai-stability-validation'
        audits.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='isolated-', dir=audits) as directory:
            env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'XDG_CONFIG_HOME': directory,
                   'TMPDIR': directory}
            result = subprocess.run([sys.executable, '-X', 'faulthandler', __file__, '--child', scenario],
                                    cwd=ROOT, env=env, capture_output=True, timeout=40)
            (audits / f'stability-{scenario}.log').write_bytes(result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0,
                             f'{scenario}: exit={result.returncode}\n' + result.stderr[-2500:].decode(errors='replace'))

    def test_parent_destruction(self): self.run_scenario('owners')
    def test_repeated_replacement(self): self.run_scenario('replacement')
    def test_queued_callbacks_after_deletion(self): self.run_scenario('queued')
    def test_mixed_repeated_sessions(self): self.run_scenario('cycles')


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--child':
        child(sys.argv[2])
    elif '--native' in sys.argv:
        IsolatedStabilityTests().run_scenario('native')
    else:
        unittest.main()
