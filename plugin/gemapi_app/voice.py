"""One-shot Qt5 microphone capture and Voxtral helpers; audio exists only in memory."""

from array import array
from io import BytesIO
import json
import sys
from uuid import uuid4
import wave

from qgis.PyQt.QtCore import (QBuffer, QElapsedTimer, QIODevice, QMetaObject, QObject,
                             QThread, QTimer, Qt, pyqtSignal, pyqtSlot)

TRANSCRIPTION_ENDPOINT = "https://api.mistral.ai/v1/audio/transcriptions"
TRANSCRIPTION_MODEL = "voxtral-mini-transcribe-3"
MAX_SECONDS = 60
MAX_AUDIO_BYTES = 48000 * 2 * 2 * MAX_SECONDS
# Retain threads if a dialog is unloaded during native device initialization.
# No QThread is destroyed while its native audio backend is still running.
_CAPTURES = set()


def wav_audio(pcm, rate, channels):
    if not 8000 <= rate <= 48000 or channels not in (1, 2):
        raise ValueError("Format microphone non accepté : PCM 16 bits, 8–48 kHz, mono ou stéréo requis.")
    frame = channels * 2
    pcm = pcm[:rate * frame * MAX_SECONDS]
    pcm = pcm[:len(pcm) // frame * frame]
    if len(pcm) < rate * frame // 4:
        raise ValueError("Audio vide ou trop court. Dictez pendant au moins un quart de seconde.")
    samples = array('h')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    if max(abs(sample) for sample in samples) < 80:
        raise ValueError("Audio silencieux ou inaudible. Vérifiez le microphone et son niveau.")
    output = BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return output.getvalue()


def context_vocabulary(names, resolution=None):
    """Current draft and a few already-proposed candidates; never a database catalogue."""
    entries = [names.get(key, '') for key in ('patrimoine', 'prestataire', 'technicien', 'type_prestation')]
    if resolution:
        for key in ('patrimoine', 'prestataire', 'technicien', 'type_prestation'):
            if key in resolution['verified']:
                entries.append(resolution['verified'][key][1])
            entries.extend(row[1] for row in resolution['pending'].get(key, [])[:3])
    entries.extend(('ouvrage hydraulique', 'stockage hydraulique', 'zone terrestre', 'débroussaillage',
                    'prestation', 'prestataire', 'technicien', 'date de début', 'date de fin', 'Terminé'))
    result, seen = [], set()
    for entry in entries:
        entry = ' '.join(str(entry).split())[:80]
        if entry and entry.casefold() not in seen and len(result) < 24:
            result.append(entry)
            seen.add(entry.casefold())
    return result


def transcription_multipart(audio, terms):
    if not audio or len(audio) > MAX_AUDIO_BYTES + 4096:
        raise ValueError("Audio vide ou trop volumineux pour une dictée de 60 secondes.")
    try:
        with wave.open(BytesIO(audio), 'rb') as wav:
            if (wav.getcomptype() != 'NONE' or wav.getsampwidth() != 2 or
                    wav.getnchannels() not in (1, 2) or not 8000 <= wav.getframerate() <= 48000 or
                    wav.getnframes() / wav.getframerate() > MAX_SECONDS):
                raise ValueError()
    except (wave.Error, EOFError, ValueError):
        raise ValueError("Fichier audio non accepté : un WAV PCM 16 bits de 60 secondes maximum est requis.") from None
    boundary = 'gemapi_app_' + uuid4().hex
    parts = []
    for name, value in [('model', TRANSCRIPTION_MODEL), ('language', 'fr'),
                        *[('context_bias', term) for term in terms[:24]]]:
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                      f'{value}\r\n').encode('utf-8'))
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="dictee.wav"\r\n'
                  'Content-Type: audio/wav\r\n\r\n').encode('ascii') + audio + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode('ascii'))
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def parse_transcription(raw):
    try:
        text = json.loads(raw)['text']
        if not isinstance(text, str) or not text.strip() or len(text) > 8000 or '\x00' in text:
            raise ValueError()
        return text.strip()
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ValueError("Voxtral n'a pas fourni de texte exploitable. Audio vide, inaudible ou réponse invalide ; poursuivez au clavier.") from None


def transcription_error(status):
    return {
        400: "Audio ou contexte non accepté par Voxtral. Réduisez la dictée et réessayez.",
        401: "Clé API Mistral invalide. Vérifiez le fichier de clé local.",
        402: "Crédit API insuffisant pour Voxtral. Vérifiez la facturation Mistral.",
        403: "Accès Voxtral non autorisé sur ce compte Mistral.",
        413: "Fichier audio trop volumineux pour Voxtral.",
        415: "Format audio non accepté par Voxtral ; un WAV PCM est requis.",
        422: "Fichier audio ou paramètres non acceptés par Voxtral.",
        429: "Quota ou crédit API Voxtral insuffisant. Vérifiez les limites et la facturation Mistral.",
    }.get(status, "Échec Voxtral : réseau interrompu ou service indisponible. Vous pouvez poursuivre au clavier.")


class _CaptureWorker(QObject):
    ready = pyqtSignal(bytes)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.audio = None
        self.buffer = None
        self.timer = None
        self.limit_timer = None
        self.clock = None
        self.format = None
        self.done = False

    @pyqtSlot()
    def start(self):
        try:
            from qgis.PyQt.QtMultimedia import QAudio, QAudioDeviceInfo, QAudioFormat, QAudioInput
        except (ImportError, OSError):
            self._fail("QtMultimedia Qt5 est indisponible dans cette installation QGIS. La saisie au clavier reste disponible.")
            return
        try:
            device = QAudioDeviceInfo.defaultInputDevice()
            if QThread.currentThread().isInterruptionRequested():
                self.cancel()
                return
            if device.isNull():
                raise ValueError("Aucun microphone disponible. Branchez ou sélectionnez un microphone dans le système.")
            fmt = QAudioFormat()
            fmt.setCodec('audio/pcm')
            fmt.setSampleRate(16000)
            fmt.setChannelCount(1)
            fmt.setSampleSize(16)
            fmt.setSampleType(QAudioFormat.SignedInt)
            fmt.setByteOrder(QAudioFormat.LittleEndian)
            if not device.isFormatSupported(fmt):
                fmt = device.nearestFormat(fmt)
            if (fmt.codec() != 'audio/pcm' or fmt.sampleSize() != 16 or
                    fmt.sampleType() != QAudioFormat.SignedInt or fmt.byteOrder() != QAudioFormat.LittleEndian or
                    not 8000 <= fmt.sampleRate() <= 48000 or fmt.channelCount() not in (1, 2)):
                raise ValueError("Le microphone ne propose pas de format WAV PCM 16 bits compatible avec Voxtral.")
            self.format = fmt
            self.buffer = QBuffer(self)
            self.buffer.open(QIODevice.WriteOnly)
            self.audio = QAudioInput(device, fmt, self)
            self.audio.stateChanged.connect(self._state_changed)
            self.audio.start(self.buffer)
            if self.audio.error() != QAudio.NoError:
                raise ValueError("Microphone inaccessible ou autorisation d'enregistrement refusée. "
                                 "Vérifiez les permissions microphone de QGIS dans Windows ou Ubuntu.")
            if self.done:
                return
            if QThread.currentThread().isInterruptionRequested():
                self.cancel()
                return
            self.clock = QElapsedTimer()
            self.clock.start()
            self.timer = QTimer(self)
            self.timer.setTimerType(Qt.PreciseTimer)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._tick)
            self.timer.start()
            self.limit_timer = QTimer(self)
            self.limit_timer.setSingleShot(True)
            self.limit_timer.setTimerType(Qt.PreciseTimer)
            self.limit_timer.timeout.connect(self.stop)
            self.limit_timer.start(MAX_SECONDS * 1000)
            self.status.emit("● Microphone actif — 0 / 60 s. Arrêter pour transcrire, ou annuler sans envoyer.")
        except Exception as error:
            self._fail(str(error) if isinstance(error, ValueError) else
                       "Microphone inaccessible. Vérifiez le périphérique et l'autorisation d'enregistrement de QGIS.")

    def _state_changed(self, state):
        from qgis.PyQt.QtMultimedia import QAudio
        if not self.done and state == QAudio.StoppedState and self.audio.error() != QAudio.NoError:
            self._fail("Microphone interrompu ou accès refusé. Vérifiez le périphérique et les permissions ; poursuivez au clavier.")

    def _tick(self):
        if QThread.currentThread().isInterruptionRequested():
            self.cancel()
            return
        elapsed = self.clock.elapsed()
        if elapsed >= MAX_SECONDS * 1000 or self.buffer.size() >= MAX_AUDIO_BYTES:
            self.stop()
        elif elapsed >= 5000 and self.buffer.size() == 0:
            self._fail("Le microphone ne fournit aucun audio. Vérifiez son accès et les autorisations d'enregistrement.")
        elif elapsed % 1000 < 100:
            self.status.emit(f"● Microphone actif — {elapsed // 1000} / 60 s. Arrêter pour transcrire, ou annuler sans envoyer.")

    def _release(self):
        self.done = True
        if self.timer is not None:
            self.timer.stop()
        if self.limit_timer is not None:
            self.limit_timer.stop()
        if self.audio is not None:
            self.audio.stop()

    def _fail(self, message):
        if self.done:
            return
        self._release()
        if self.buffer is not None:
            self.buffer.close()
            self.buffer.setData(b'')
        self.failed.emit(message)
        self.finished.emit()

    @pyqtSlot()
    def stop(self):
        if self.done:
            return
        if QThread.currentThread().isInterruptionRequested():
            self.cancel()
            return
        self._release()
        try:
            if self.buffer is None or self.format is None:
                raise ValueError("Audio vide. Vous pouvez poursuivre au clavier.")
            pcm = bytes(self.buffer.data())
            self.buffer.close()
            self.buffer.setData(b'')
            audio = wav_audio(pcm, self.format.sampleRate(), self.format.channelCount())
            self.ready.emit(audio)
        except ValueError as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

    @pyqtSlot()
    def cancel(self):
        if not self.done:
            self._release()
            if self.buffer is not None:
                self.buffer.close()
                self.buffer.setData(b'')
            self.finished.emit()


class Recorder(QObject):
    ready = pyqtSignal(bytes)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None

    def start(self):
        if self.thread is not None:
            return
        thread = QThread()  # Outlives a closing dialog until native capture has stopped.
        worker = _CaptureWorker()
        thread.worker = worker
        worker.moveToThread(thread)
        worker.ready.connect(self.ready)
        worker.failed.connect(self.failed)
        worker.status.connect(self.status)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.started.connect(worker.start)
        thread.finished.connect(self._finished)
        thread.finished.connect(lambda: _CAPTURES.discard(thread))
        thread.finished.connect(thread.deleteLater)
        _CAPTURES.add(thread)
        self.thread = thread
        thread.start()

    def stop(self):
        if self.thread is not None:
            try:
                QMetaObject.invokeMethod(self.thread.worker, 'stop', Qt.QueuedConnection)
            except RuntimeError:  # Native teardown may precede delivery of thread.finished.
                pass

    def cancel(self):
        if self.thread is not None:
            try:
                self.thread.requestInterruption()
                QMetaObject.invokeMethod(self.thread.worker, 'cancel', Qt.QueuedConnection)
            except RuntimeError:
                pass

    def _finished(self):
        self.thread = None
        self.finished.emit()
