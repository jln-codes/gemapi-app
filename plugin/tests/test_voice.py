"""Voxtral transport, review and Qt capture simulations. No microphone or API required."""

from array import array
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from qgis.PyQt.QtCore import QObject, QSettings, QTimer, pyqtSignal
from qgis.PyQt.QtMultimedia import QAudio, QAudioFormat
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.voice import (MAX_SECONDS, Recorder, _CaptureWorker, context_vocabulary,
                                   parse_transcription, transcription_error, transcription_multipart, wav_audio)
from gemapi_app.voice import (MAX_SPEECH_RESPONSE, SPEECH_SETTING, SPEECH_TIMEOUT_MS, Speaker,
                             _PLAYBACKS, _PlaybackWorker, parse_speech, speech_payload)
from gemapi_app.assistant import Draft, spoken_result
import test_assistant_qgis as fixtures
from test_assistant import CATALOG, COMPLETE_PHRASE, FULL, PHRASE, response


def pcm(seconds=1, rate=16000, channels=1):
    return array('h', [500, -500] * (int(seconds * rate * channels) // 2)).tobytes()


def audio():
    return wav_audio(pcm(), 16000, 1)


def speech_response(data=None):
    return json.dumps({'audio_data': base64.b64encode(audio() if data is None else data).decode('ascii')}).encode()


class SpeechReply(fixtures.Reply):
    def setReadBufferSize(self, size):
        self.buffer_limit = size


class SpeechHelpersTests(unittest.TestCase):
    def test_official_request_and_bounded_input(self):
        self.assertEqual(speech_payload('Bonjour.'), {
            'model': 'voxtral-mini-tts-3-0', 'input': 'Bonjour.',
            'voice_id': 'voice_592', 'response_format': 'wav'})
        for text in ('', 'a' * 361, 'Bonjour\x00', None, {'secret': 'never send'}):
            with self.assertRaises(ValueError):
                speech_payload(text)

    def test_base64_wav_decoded_and_truncated_or_invalid_formats_refused(self):
        samples, rate, channels = parse_speech(speech_response())
        self.assertEqual((samples, rate, channels), (pcm(), 16000, 1))
        invalid = (b'{}', b'null', b'broken', b'{"audio_data":3}', b'{"audio_data":"!!"}',
                   b'{"audio_data":""}', speech_response(b'not wav'), speech_response(audio()[:-2]),
                   speech_response(audio() + b'extra'), b' ' * (MAX_SPEECH_RESPONSE + 1))
        for raw in invalid:
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                parse_speech(raw)
        for seconds, width, rate in ((31, 2, 16000), (1, 1, 16000), (1, 2, 96000), (0, 2, 16000)):
            output = BytesIO()
            with wave.open(output, 'wb') as wav:
                wav.setparams((1, width, rate, 0, 'NONE', 'uncompressed'))
                wav.writeframes(b'\0' * seconds * width * rate)
            with self.assertRaises(ValueError):
                parse_speech(speech_response(output.getvalue()))

    def test_only_locally_verified_facts_no_raw_json_names_ids_or_save_claim(self):
        draft = Draft()
        draft.apply(fixtures.proposal(**{**FULL, 'date_fin': None, 'description': '/private/sensitive.txt',
                                        'message': 'Prestation enregistrée ! Message privé à ignorer.'}),
                    user_message=PHRASE)
        result = draft.resolve(CATALOG)
        text = spoken_result(draft, result)
        self.assertIn('identifiés', text)
        self.assertIn('manque la date de fin', text)
        for private in ('enregistrée', 'Jean', 'Veolia', '/private', fixtures.uid(6), '{', '"'):
            self.assertNotIn(private, text)
        self.assertEqual(spoken_result(draft, None), '')
        draft.apply(fixtures.proposal(date_fin='MEME_JOUR'), user_message='Le même jour.')
        text = spoken_result(draft, draft.resolve(CATALOG))
        self.assertIn('brouillon est complet', text)
        self.assertIn("Rien n'est encore enregistré", text)
        draft.end_date_needs_confirmation = True
        self.assertIn('doit être confirmée', spoken_result(draft, draft.resolve(CATALOG)))
        result['pending']['patrimoine'] = [CATALOG['patrimoine'][0]] * 2
        self.assertIn('Plusieurs objets patrimoniaux', spoken_result(draft, result))


class SpeechDialogTests(unittest.TestCase):
    tearDown = fixtures.QtAssistantTests.tearDown

    def setUp(self):
        folder = Path(__file__).resolve().parents[2] / 'audits'
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='tts-settings-', dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.settings = QSettings(str(Path(self.temp.name) / 'profile.ini'), QSettings.IniFormat)
        patcher = patch('gemapi_app.assistant_dialog.QSettings', return_value=self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        fixtures.QtAssistantTests.setUp(self)
        self.dialog.recorder = FakeRecorder(self.dialog)
        self.play = self.stack.enter_context(patch.object(self.dialog.speaker, '_play'))

    def deliver(self, fields=None, speech_raw=None, status=200):
        small = fixtures.Reply(response(**(FULL if fields is None else fields)))
        speech = SpeechReply(speech_response() if speech_raw is None else speech_raw, status)
        self.manager.post.side_effect = [small, speech]
        self.dialog.submit_user_message(COMPLETE_PHRASE)
        small.complete()
        return speech

    def test_disabled_by_default_no_tts_and_preference_persisted_without_request(self):
        self.assertFalse(self.dialog.speech_enabled.isChecked())
        self.deliver()
        self.assertEqual(self.manager.post.call_count, 1)
        self.play.assert_not_called()
        self.dialog.speech_enabled.setChecked(True)
        self.assertTrue(self.settings.value(SPEECH_SETTING, False, type=bool))
        self.assertEqual(self.manager.post.call_count, 1)
        other = fixtures.AssistantDialog(self.session, self.open_draft, self.parent)
        self.assertTrue(other.speech_enabled.isChecked())
        other.close()
        other.deleteLater()
        self.dialog.speech_enabled.setChecked(False)
        self.assertFalse(self.settings.value(SPEECH_SETTING, True, type=bool))

    def test_verified_short_reply_and_cached_replay_no_second_small_or_tts_call(self):
        self.dialog.speech_enabled.setChecked(True)
        reply = self.deliver()
        request, body = self.manager.post.call_args.args
        self.assertEqual(request.url().toString(), 'https://api.mistral.ai/v1/audio/speech')
        self.assertEqual(set(json.loads(body)), {'model', 'input', 'voice_id', 'response_format'})
        self.assertNotIn(b'Jean', body)
        self.assertNotIn(b'Rivi', body)
        self.assertEqual(reply.buffer_limit, MAX_SPEECH_RESPONSE + 1)
        self.assertTrue(self.dialog.input.isEnabled())
        self.assertTrue(self.dialog.open_button.isEnabled())
        reply.complete()
        self.play.assert_called_once()
        self.assertIsNotNone(self.dialog.speaker.audio)
        with patch('gemapi_app.assistant_dialog.read_api_key', side_effect=ValueError('absent')):
            self.dialog.replay_button.click()
        self.assertEqual(self.play.call_count, 2)
        self.assertEqual(self.manager.post.call_count, 2)
        self.open_draft.assert_not_called()
        self.session.db.executeSql.assert_not_called()

    def test_stop_disable_and_stale_response_never_play(self):
        self.dialog.speech_enabled.setChecked(True)
        old = self.deliver()
        self.dialog.stop_speech_button.click()
        self.assertTrue(old.aborted)
        self.assertFalse(self.dialog.speaker.timer.isActive())
        old.complete()
        self.play.assert_not_called()
        self.assertTrue(self.dialog.replay_button.isEnabled())
        self.dialog.speech_enabled.setChecked(False)
        self.dialog._replay_speech()
        self.assertFalse(self.dialog.replay_button.isEnabled())
        self.assertEqual(self.manager.post.call_count, 2)

    def test_newer_request_and_old_timeout_do_not_play_old_answer(self):
        self.dialog.speech_enabled.setChecked(True)
        old = self.deliver({**FULL, 'date_fin': None})
        new = self.deliver()
        self.assertTrue(old.aborted)
        self.dialog.speaker._read(old)
        self.dialog.speaker._finished(old)
        self.dialog.speaker._timeout(old)
        old.complete()
        self.assertIs(self.dialog.speaker.reply, new)
        self.assertTrue(self.dialog.speaker.timer.isActive())
        self.play.assert_not_called()
        new.complete()
        self.play.assert_called_once()
        self.assertIn('brouillon est complet', self.dialog.speaker.text)

    def test_microphone_input_and_corrections_interrupt_without_losing_staged_data(self):
        self.dialog.speech_enabled.setChecked(True)
        old = self.deliver({**FULL, 'date_fin': None})
        self.dialog.date_edits['date_fin'].setText('12/11/2026')
        self.assertTrue(old.aborted)
        self.assertEqual(self.dialog.date_edits['date_fin'].text(), '12/11/2026')
        self.assertNotIn('date_fin', self.dialog.draft.names)
        self.dialog.input.setPlainText('Note encore à envoyer')
        self.dialog._toggle_microphone()
        self.assertTrue(self.dialog._recording)
        self.dialog._cancel_voice()
        self.assertEqual(self.dialog.input.toPlainText(), 'Note encore à envoyer')
        old.complete()
        self.play.assert_not_called()

    def test_hide_close_cancel_and_new_prestation_release_network_and_audio(self):
        self.dialog.speech_enabled.setChecked(True)
        for action in ('hide', 'cancel_request', 'close'):
            self.dialog.show()
            old = self.deliver()
            before = dict(self.dialog.draft.names)
            getattr(self.dialog, action)()
            self.assertTrue(old.aborted)
            old.complete()
            self.assertIsNone(self.dialog.speaker.audio)
            self.assertFalse(self.dialog.speaker.raw)
            self.assertEqual(self.dialog.draft.names, before)
        self.dialog.show()
        old = self.deliver()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.dialog.new_prestation()
        old.complete()
        self.assertEqual(self.dialog.draft.names, {})
        self.assertEqual(self.dialog.speaker.text, '')
        self.play.assert_not_called()

    def test_network_invalid_audio_timeout_and_missing_key_keep_draft(self):
        self.dialog.speech_enabled.setChecked(True)
        for raw, status in ((b'private server details', 503), (b'{"audio_data":"!!"}', 200)):
            reply = self.deliver(speech_raw=raw, status=status)
            before = dict(self.dialog.draft.names)
            reply.complete()
            self.assertEqual(self.dialog.draft.names, before)
            self.assertTrue(self.dialog.input.isEnabled())
            self.assertTrue(self.dialog.open_button.isEnabled())
            self.assertNotIn('private server details', self.dialog.history.toPlainText())
            self.assertFalse(self.dialog.speaker.raw)
        reply = self.deliver()
        self.assertEqual(self.dialog.speaker.timer.interval(), SPEECH_TIMEOUT_MS)
        self.dialog.speaker._timeout(reply)
        self.assertTrue(reply.aborted)
        self.assertIn('dépassé', self.dialog.speech_status.text())
        with patch('gemapi_app.assistant_dialog.read_api_key', side_effect=['key-for-small', ValueError('missing')]):
            count = self.manager.post.call_count
            self.deliver()
        self.assertEqual(self.manager.post.call_count, count + 1)
        self.assertIn('Clé Mistral indisponible', self.dialog.speech_status.text())
        self.play.assert_not_called()
        self.session.db.executeSql.assert_not_called()

    def test_oversized_response_aborts_and_does_not_block_loop(self):
        self.dialog.speech_enabled.setChecked(True)
        reply = self.deliver(speech_raw=b'x' * (MAX_SPEECH_RESPONSE + 1))
        ticks = []
        QTimer.singleShot(1, lambda: ticks.append(True))
        reply.complete()
        QTest.qWait(20)
        self.assertTrue(ticks)
        self.assertTrue(reply.aborted)
        self.assertIn('volumineuse', self.dialog.speech_status.text())
        self.play.assert_not_called()

    def test_no_tts_without_successful_local_verification(self):
        self.dialog.speech_enabled.setChecked(True)
        with patch('gemapi_app.assistant_dialog.load_catalog', side_effect=[CATALOG, RuntimeError('private SQL')]):
            self.deliver()
        self.assertEqual(self.manager.post.call_count, 1)
        self.assertEqual(self.dialog.speaker.text, '')
        self.assertIsNone(self.dialog.resolution)
        self.assertFalse(self.dialog.open_button.isEnabled())
        self.assertNotIn('private SQL', self.dialog.history.toPlainText())
        self.play.assert_not_called()


class FakeOutput(QObject):
    stateChanged = pyqtSignal(int)

    def __init__(self, *args):
        super().__init__()

    def start(self, buffer):
        self.buffer = buffer

    def stop(self):
        pass

    def error(self):
        return QAudio.NoError


class PlaybackTests(unittest.TestCase):
    def device(self):
        device = Mock()
        device.isNull.return_value = False
        device.isFormatSupported.return_value = True
        return device

    def test_native_output_is_destroyed_before_buffer_release_and_thread_finish(self):
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioOutput', FakeOutput):
            worker = _PlaybackWorker(parse_speech(speech_response()))
            worker.start()
            order = []
            buffer = worker.buffer
            def destroyed(_object=None):
                self.assertTrue(buffer.isOpen())
                self.assertFalse(worker.signalsBlocked())
                self.app.processEvents()  # PulseAudio destructor can reenter the event loop.
                order.append('device')
            worker.output.destroyed.connect(destroyed)
            worker.finished.connect(lambda: order.append('finished'))
            worker.cancel()
            self.assertEqual(order, ['device', 'finished'])
            self.assertIsNone(worker.buffer)

    def test_end_of_finite_audio_is_not_reported_as_device_failure(self):
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioOutput', FakeOutput):
            worker = _PlaybackWorker(parse_speech(speech_response()))
            errors = []
            worker.failed.connect(lambda _generation, text: errors.append(text))
            worker.start()
            worker.buffer.seek(worker.buffer.size())
            worker.output.error = lambda: QAudio.UnderrunError
            worker.output.stateChanged.emit(QAudio.IdleState)
            QTest.qWait(5)
            self.assertTrue(worker.done)
            self.assertFalse(errors)

    def test_memory_only_player_completion_cancel_and_device_failures(self):
        errors = []
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioOutput', FakeOutput):
            worker = _PlaybackWorker(parse_speech(speech_response()))
            worker.failed.connect(lambda _generation, text: errors.append(text))
            worker.start()
            self.assertTrue(worker.buffer.isOpen())
            worker.output.stateChanged.emit(QAudio.IdleState)
            QTest.qWait(5)
            self.assertIsNone(worker.buffer)
            self.assertIsNone(worker.output)
            self.assertEqual(worker.pcm, b'')
            self.assertFalse(worker.timer.isActive())
            worker.cancel()
        self.assertFalse(errors)
        for condition in ('missing', 'unsupported', 'backend', 'module'):
            worker = _PlaybackWorker(parse_speech(speech_response()))
            worker.failed.connect(lambda _generation, text: errors.append(text))
            device = self.device()
            device.isNull.return_value = condition == 'missing'
            device.isFormatSupported.return_value = condition != 'unsupported'
            output = FakeOutput()
            output.error = lambda: QAudio.OpenError
            with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=device), patch(
                    'qgis.PyQt.QtMultimedia.QAudioOutput', return_value=output):
                if condition == 'module':
                    with patch.dict(sys.modules, {'qgis.PyQt.QtMultimedia': None}):
                        worker.start()
                else:
                    worker.start()
            self.assertTrue(worker.done)
            self.assertIsNone(worker.buffer)
        self.assertEqual(len(errors), 4)

    def test_worker_threads_reactive_interruptible_and_no_qt_resource_retained(self):
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioOutput', FakeOutput):
            speaker = Speaker()
            speaker.set_text('Le brouillon reste à vérifier.')
            speaker.audio = parse_speech(speech_response())
            ticks, statuses = [], []
            speaker.status.connect(statuses.append)
            speaker.speak(Mock(), '')
            QTimer.singleShot(1, lambda: ticks.append(True))
            for _ in range(60):
                QTest.qWait(10)
                if ticks and statuses:
                    break
            self.assertTrue(ticks)
            self.assertIn('Lecture de la réponse…', statuses)
            speaker.stop()
            speaker.speak(Mock(), '')
            speaker.stop(clear=True)
            for _ in range(60):
                QTest.qWait(10)
                if not _PLAYBACKS:
                    break
            self.assertFalse(_PLAYBACKS)
            self.assertIsNone(speaker.thread)
            self.assertIsNone(speaker.audio)
            speaker.deleteLater()

    def test_fast_deleted_worker_keeps_queued_error_and_never_reports_false_success(self):
        from qgis.PyQt.QtCore import QThread
        device = self.device()
        device.isNull.return_value = True
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultOutputDevice', return_value=device):
            speaker = Speaker()
            speaker.set_text('Réponse de test.')
            speaker.audio = parse_speech(speech_response())
            statuses = []
            speaker.status.connect(statuses.append)
            speaker.speak(Mock(), '')
            QThread.msleep(30)  # Let the worker die before its queued messages are delivered.
            for _ in range(60):
                QTest.qWait(5)
                if not _PLAYBACKS:
                    break
            self.assertTrue(any('indisponible' in text for text in statuses), statuses)
            self.assertFalse(any('Lecture terminée' in text for text in statuses), statuses)
            speaker.stop(clear=True)
            speaker.deleteLater()


class VoiceHelpersTests(unittest.TestCase):
    def test_wav_pcm_and_sixty_second_limit(self):
        data = wav_audio(pcm(61), 16000, 1)
        with wave.open(BytesIO(data)) as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnframes() / wav.getframerate(), MAX_SECONDS)

    def test_empty_silence_and_unsupported_format(self):
        for data, rate, channels in ((b'', 16000, 1), (b'\0' * 32000, 16000, 1),
                                     (pcm(), 96000, 1), (pcm(), 16000, 8)):
            with self.assertRaises(ValueError):
                wav_audio(data, rate, channels)
        for invalid in (b'not wav', b'', b'RIFFtruncated'):
            with self.assertRaises(ValueError):
                transcription_multipart(invalid, [])

    def test_official_multipart_with_context_bias(self):
        vocabulary = context_vocabulary(FULL)
        data, content_type = transcription_multipart(audio(), vocabulary)
        self.assertIn('multipart/form-data; boundary=gemapi_app_', content_type)
        self.assertIn(b'name="model"\r\n\r\nvoxtral-mini-transcribe-3', data)
        self.assertIn(b'name="language"\r\n\r\nfr', data)
        self.assertIn(b'filename="dictee.wav"', data)
        self.assertIn('Rivière du Buissons'.encode(), data)
        self.assertEqual(data.count(b'name="context_bias"'), len(vocabulary))

    def test_context_bounded_to_draft_and_candidates(self):
        pending = {'patrimoine': [(str(i), 'Ouvrage ' + str(i), '') for i in range(200)]}
        terms = context_vocabulary(FULL, {'verified': {}, 'pending': pending})
        self.assertLessEqual(len(terms), 24)
        self.assertLessEqual(sum(map(len, terms)), 24 * 80)
        self.assertIn('Ouvrage 2', terms)
        self.assertNotIn('Ouvrage 3', terms)
        self.assertIn('Jean Dubois', terms)
        self.assertNotIn('Pierre Martin', terms)

    def test_transcription_empty_invalid_and_network_errors(self):
        self.assertEqual(parse_transcription(b'{"text":"  Bonjour  "}'), 'Bonjour')
        for raw in (b'broken', b'{}', b'{"text":""}', b'{"text":null}'):
            with self.assertRaises(ValueError):
                parse_transcription(raw)
        for status, fragment in ((401, 'Clé'), (402, 'Crédit'), (403, 'non autorisé'), (429, 'Quota'),
                                 (415, 'Format'), (422, 'audio'), (503, 'réseau')):
            self.assertIn(fragment, transcription_error(status))


class FakeRecorder(QObject):
    ready = pyqtSignal(bytes)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    thread = None

    def __init__(self, parent):
        super().__init__(parent)
        self.start = Mock()
        self.stop = Mock()
        self.cancel = Mock()


class VoiceDialogTests(unittest.TestCase):
    tearDown = fixtures.QtAssistantTests.tearDown
    send = fixtures.QtAssistantTests.send

    def setUp(self):
        fixtures.QtAssistantTests.setUp(self)
        self.recorder = FakeRecorder(self.dialog)
        self.dialog.recorder = self.recorder
        self.recorder.finished.connect(self.dialog._voice_finished)

    def start_voice_request(self, raw=b'{"text":"Jean Dubois"}', status=200):
        reply = fixtures.Reply(raw, status)
        self.manager.post.return_value = reply
        self.dialog._toggle_microphone()
        self.recorder.start.assert_called_once()
        self.recorder.ready.emit(audio())
        return reply

    def test_oversized_finished_reply_is_completed_only_once_during_abort(self):
        reply = self.start_voice_request(b'x' * (1024 * 1024 + 1))
        reply.finished.emit()  # A final unread buffer can abort inside finished itself.
        self.assertTrue(reply.aborted)
        self.assertEqual(self.dialog.history.toPlainText().count('Réponse Voxtral trop volumineuse'), 1)
        self.recorder.start.reset_mock()
        small = self.send('Demande de test.', b'x' * (1024 * 1024 + 1))
        small.finished.emit()
        self.assertTrue(small.aborted)
        self.assertEqual(self.dialog.history.toPlainText().count('Réponse Mistral trop volumineuse'), 1)

    def test_transcription_is_visible_editable_and_requires_send(self):
        self.dialog.input.setPlainText('Note déjà saisie.')
        reply = self.start_voice_request(json.dumps({'text': PHRASE}).encode())
        self.assertEqual(self.manager.post.call_count, 1)
        request, body = self.manager.post.call_args.args
        self.assertTrue(request.url().path().endswith('/audio/transcriptions'))
        self.assertIn(b'voxtral-mini-transcribe-3', body)
        self.assertTrue(self.dialog.input.isEnabled())
        self.assertFalse(self.dialog.send_button.isEnabled())
        reply.complete()
        self.assertEqual(self.manager.post.call_count, 1)  # Never auto-submit a transcript to Small.
        self.assertIn('Vous — dictée à vérifier (Voxtral)', self.dialog.history.toPlainText())
        self.assertIn(PHRASE, self.dialog.input.toPlainText())
        self.assertIn('Note déjà saisie.', self.dialog.input.toPlainText())
        self.assertTrue(self.dialog.send_button.isEnabled())
        self.dialog.input.setPlainText(PHRASE + ' Le technicien est Pierre Martin.')
        self.send(self.dialog.input.toPlainText(), response(**{**FULL, 'technicien': 'Pierre Martin'})).complete()
        self.assertEqual(self.manager.post.call_count, 2)
        self.assertEqual(self.dialog.draft.names['technicien'], 'Pierre Martin')
        self.session.db.executeSql.assert_not_called()

    def test_cancel_recording_never_sends_audio_even_if_ready_arrives_late(self):
        self.dialog._toggle_microphone()
        self.assertTrue(self.dialog._recording)
        self.assertTrue(self.dialog.input.isEnabled())
        self.recorder.status.emit('● Microphone actif')
        self.assertIn('actif', self.dialog.voice_status.text())
        self.dialog._cancel_voice()
        self.recorder.cancel.assert_called_once()
        self.recorder.ready.emit(audio())
        self.manager.post.assert_not_called()
        self.assertFalse(self.dialog._recording)
        self.assertIn('aucun audio envoyé', self.dialog.voice_status.text())
        self.assertTrue(self.dialog.send_button.isEnabled())

    def test_new_during_empty_recording_cancels_and_ignores_old_capture_callbacks(self):
        self.dialog._toggle_microphone()
        stale_slots = [slot for _signal, slot in self.dialog._capture_slots]
        self.assertTrue(self.dialog.new_button.isEnabled())
        with patch.object(QMessageBox, 'question') as question:
            self.assertTrue(self.dialog.new_prestation())
            question.assert_not_called()
        self.recorder.cancel.assert_called_once()
        self.assertFalse(self.dialog._recording)
        self.assertEqual(self.dialog._capture_slots, [])
        self.dialog._toggle_microphone()
        status = self.dialog.voice_status.text()
        stale_slots[0](audio())
        stale_slots[1]('Ancienne erreur micro')
        stale_slots[2]('Ancien statut micro')
        self.assertTrue(self.dialog._recording)
        self.assertEqual(self.dialog.voice_status.text(), status)
        self.manager.post.assert_not_called()
        self.assertEqual(self.recorder.start.call_count, 2)
        reply = fixtures.Reply(json.dumps({'text': 'Dictée suivante'}).encode('utf-8'))
        self.manager.post.return_value = reply
        self.recorder.ready.emit(audio())
        self.assertIs(self.dialog._voice_reply, reply)
        self.assertEqual(self.manager.post.call_count, 1)

    def test_new_during_voxtral_upload_ignores_old_result_and_keeps_new_timer(self):
        old = self.start_voice_request(b'{"text":"Ancienne transcription"}')
        self.assertTrue(self.dialog.new_button.isEnabled())
        with patch.object(QMessageBox, 'question') as question:
            self.dialog.new_prestation()
            question.assert_not_called()
        self.assertTrue(old.aborted)
        self.assertIsNone(self.dialog._voice_reply)
        self.assertFalse(self.dialog.voice_timer.isActive())
        new = fixtures.Reply(b'{"text":"Nouvelle transcription"}', 200)
        self.manager.post.return_value = new
        self.dialog._toggle_microphone()
        self.recorder.ready.emit(audio())
        self.dialog._read_voice_response(old)
        self.dialog._voice_response_finished(old)
        self.dialog._voice_timeout(old)
        old.complete()
        self.assertIs(self.dialog._voice_reply, new)
        self.assertTrue(self.dialog.voice_timer.isActive())
        self.assertEqual(self.dialog.input.toPlainText(), '')
        new.complete()
        self.assertEqual(self.dialog.input.toPlainText(), 'Nouvelle transcription')
        self.assertNotIn('Ancienne transcription', self.dialog.history.toPlainText())
        self.assertEqual(self.manager.post.call_count, 2)
        self.session.db.executeSql.assert_not_called()

    def test_new_after_transcription_requires_confirmation_keeps_history_and_clears_input(self):
        reply = self.start_voice_request(b'{"text":"Observation vocale unique"}')
        reply.complete()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.assertFalse(self.dialog.new_prestation())
        self.assertEqual(self.dialog.input.toPlainText(), 'Observation vocale unique')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.assertTrue(self.dialog.new_prestation())
        self.assertEqual(self.dialog.input.toPlainText(), '')
        self.assertIn('Observation vocale unique', self.dialog.history.toPlainText())
        self.assertFalse(self.dialog._review_required)
        self.send('Autre demande au clavier.', response(description='Note suivante')).complete()
        payload = json.loads(self.manager.post.call_args.args[1])
        self.assertEqual(json.loads(payload['messages'][1]['content'])['brouillon'], {})
        self.assertNotIn('Observation vocale unique', json.dumps(payload))
        self.session.db.executeSql.assert_not_called()

    def test_new_during_recording_with_existing_draft_requires_one_confirmation_and_clears_bias(self):
        self.send(COMPLETE_PHRASE, response(**FULL)).complete()
        self.dialog._toggle_microphone()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No) as question:
            self.assertFalse(self.dialog.new_prestation())
            question.assert_called_once()
        self.assertTrue(self.dialog._recording)
        self.recorder.cancel.assert_not_called()
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes) as question:
            self.assertTrue(self.dialog.new_prestation())
            question.assert_called_once()
        self.recorder.cancel.assert_called_once()
        self.assertEqual(self.dialog.draft.names, {})
        reply = fixtures.Reply(b'{"text":"Autre demande"}')
        self.manager.post.return_value = reply
        self.dialog._toggle_microphone()
        self.recorder.ready.emit(audio())
        body = self.manager.post.call_args.args[1]
        self.assertNotIn('Jean Dubois'.encode('utf-8'), body)
        self.assertNotIn('Rivière du Buissons'.encode('utf-8'), body)
        self.assertEqual(self.manager.post.call_count, 2)
        self.session.db.executeSql.assert_not_called()

    def test_draft_survives_keyboard_then_voice_date_then_name_correction(self):
        self.send(PHRASE, response(**{**FULL, 'date_fin': None})).complete()
        self.assertFalse(self.dialog.open_button.isEnabled())
        self.start_voice_request(json.dumps({'text': 'Le même jour.'}).encode()).complete()
        self.assertNotIn('date_fin', self.dialog.draft.names)
        self.send(self.dialog.input.toPlainText(), response(date_fin='MEME_JOUR')).complete()
        self.assertTrue(self.dialog.open_button.isEnabled())
        self.recorder.start.reset_mock()
        self.start_voice_request(b'{"text":"Le technicien est Pierre Martin."}').complete()
        self.assertEqual(self.dialog.draft.names['technicien'], 'Jean Dubois')
        self.send(self.dialog.input.toPlainText(), response(technicien='Pierre Martin')).complete()
        self.dialog.open_button.click()
        values, _ = self.open_draft.call_args.args
        self.assertEqual(values['technicien_id'], CATALOG['technicien'][1][0])
        self.assertEqual(values['date_fin'], '2026-11-11')
        self.session.db.executeSql.assert_not_called()

    def test_audio_errors_preserve_history_and_keyboard(self):
        for message in ('Aucun microphone disponible.', "Autorisation d'enregistrement refusée.",
                        'Audio vide.', 'Audio inaudible.', 'QtMultimedia indisponible.'):
            self.dialog._toggle_microphone()
            self.recorder.failed.emit(message)
            self.assertIn(message, self.dialog.history.toPlainText())
            self.assertTrue(self.dialog.input.isEnabled())
            self.assertTrue(self.dialog.send_button.isEnabled())
        self.manager.post.assert_not_called()

    def test_voxtral_http_failures_do_not_expose_bodies(self):
        for status, fragment in ((401, 'Clé'), (402, 'Crédit'), (403, 'non autorisé'),
                                 (415, 'Format'), (429, 'Quota'), (503, 'réseau')):
            self.recorder.start.reset_mock()
            reply = self.start_voice_request(b'private-error-response', status)
            reply.complete()
            self.assertIn(fragment, self.dialog.voice_status.text())
            self.assertNotIn('private-error-response', self.dialog.history.toPlainText())
            self.assertTrue(self.dialog.input.isEnabled())
            self.assertTrue(self.dialog.send_button.isEnabled())
            self.assertFalse(self.dialog._voice_raw)

    def test_timeout_cancel_upload_and_close(self):
        reply = self.start_voice_request()
        ticks = []
        QTimer.singleShot(5, lambda: ticks.append(True))
        for _ in range(40):
            QTest.qWait(10)
            if ticks:
                break
        self.assertTrue(ticks)
        self.dialog._voice_timeout()
        self.assertTrue(reply.aborted)
        self.assertIn('Délai Voxtral dépassé', self.dialog.history.toPlainText())
        self.recorder.start.reset_mock()
        reply = self.start_voice_request()
        self.dialog._cancel_voice()
        self.assertTrue(reply.aborted)
        self.assertIsNone(self.dialog._voice_reply)
        self.recorder.start.reset_mock()
        reply = self.start_voice_request()
        self.dialog.reject()
        self.assertTrue(reply.aborted)
        self.assertGreater(len(self.dialog.messages), 1)

    def test_missing_key_and_invalid_transcript_preserve_draft(self):
        self.send(COMPLETE_PHRASE, response(**FULL)).complete()
        previous = dict(self.dialog.draft.names)
        with patch('gemapi_app.assistant_dialog.read_api_key', side_effect=ValueError('Clé absente.')):
            self.dialog._toggle_microphone()
            count = self.manager.post.call_count
            self.recorder.ready.emit(audio())
            self.assertEqual(self.manager.post.call_count, count)
        self.recorder.start.reset_mock()
        reply = self.start_voice_request(b'{"text":""}')
        reply.complete()
        self.assertIn('Audio vide', self.dialog.history.toPlainText())
        self.assertEqual(self.dialog.draft.names, previous)
        self.assertTrue(self.dialog.input.isEnabled())


class FakeAudio(QObject):
    stateChanged = pyqtSignal(int)

    def __init__(self, *args):
        super().__init__()

    def start(self, buffer):
        buffer.write(pcm())

    def error(self):
        return QAudio.NoError

    def stop(self):
        pass


class CaptureWorkerTests(unittest.TestCase):
    def device(self):
        device = Mock()
        device.isNull.return_value = False
        device.isFormatSupported.return_value = True
        return device

    def test_capture_pcm_timer_limit_and_cancel(self):
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultInputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioInput', FakeAudio):
            worker = _CaptureWorker()
            ready, errors = [], []
            worker.ready.connect(ready.append)
            worker.failed.connect(errors.append)
            worker.start()
            self.assertEqual(worker.limit_timer.interval(), 60000)
            worker.stop()
            self.assertEqual(len(ready), 1)
            self.assertFalse(errors)
            self.assertTrue(ready[0].startswith(b'RIFF'))
            self.assertEqual(worker.buffer.size(), 0)
            worker2 = _CaptureWorker()
            worker2.ready.connect(ready.append)
            worker2.start()
            worker2.cancel()
            worker2._tick()  # An already queued timer must not touch released audio.
            self.assertEqual(len(ready), 1)
            self.assertEqual(worker2.buffer.size(), 0)

    def test_absent_device_permission_denied_and_missing_qtmultimedia(self):
        device = self.device()
        device.isNull.return_value = True
        worker = _CaptureWorker()
        errors = []
        worker.failed.connect(errors.append)
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultInputDevice', return_value=device):
            worker.start()
        self.assertIn('Aucun microphone', errors[0])
        worker = _CaptureWorker()
        worker.failed.connect(errors.append)
        audio_backend = FakeAudio()
        audio_backend.error = lambda: QAudio.OpenError
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultInputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioInput', return_value=audio_backend):
            worker.start()
        self.assertIn('autorisation', errors[-1])
        worker = _CaptureWorker()
        worker.failed.connect(errors.append)
        with patch.dict(sys.modules, {'qgis.PyQt.QtMultimedia': None}):
            worker.start()
        self.assertIn('QtMultimedia', errors[-1])

    def test_capture_thread_keeps_main_loop_reactive_and_stops_cleanly(self):
        with patch('qgis.PyQt.QtMultimedia.QAudioDeviceInfo.defaultInputDevice', return_value=self.device()), patch(
                'qgis.PyQt.QtMultimedia.QAudioInput', FakeAudio):
            recorder = Recorder()
            messages, ticks = [], []
            recorder.status.connect(messages.append)
            recorder.start()
            try:
                QTimer.singleShot(5, lambda: ticks.append(True))
                for _ in range(40):
                    QTest.qWait(10)
                    if messages and ticks:
                        break
                self.assertTrue(ticks)
                self.assertTrue(messages)
            finally:
                recorder.cancel()
                for _ in range(40):
                    QTest.qWait(10)
                    if recorder.thread is None:
                        break
            self.assertIsNone(recorder.thread)


def setUpModule():
    global APP
    APP = QgsApplication([], True)
    APP.initQgis()
    VoiceDialogTests.app = APP
    CaptureWorkerTests.app = APP
    SpeechDialogTests.app = APP
    PlaybackTests.app = APP


def tearDownModule():
    APP.exitQgis()


if __name__ == '__main__':
    unittest.main()
