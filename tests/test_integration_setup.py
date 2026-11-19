"""Pure configuration/script checks; these tests do not start any service."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.launch import ROOT,load_env,command_for,network_settings,validate_url
from scripts.verify import stages,console_text


class SetupTests(unittest.TestCase):
    def test_console_preserves_logs_without_cp1252_print_crash(self):
        with patch('scripts.verify.sys.stdout',SimpleNamespace(encoding='cp1252')):
            self.assertEqual(console_text('\u2713 test passed'),'\\u2713 test passed')

    def test_env_is_inert_and_process_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('# comment\nWORKER_ID="local-1"\nMASTER_URL=http://127.0.0.1:8000\nLITERAL=$(do-not-execute)\n',encoding='utf-8')
            values=load_env(path,{'WORKER_ID':'terminal-worker'})
        self.assertEqual(values['WORKER_ID'],'terminal-worker')
        self.assertEqual(values['LITERAL'],'$(do-not-execute)')

    def test_invalid_configuration_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env';path.write_text('bad key=value',encoding='utf-8')
            with self.assertRaises(ValueError):load_env(path,{})
        for environment in [{'MASTER_PORT':'0'},{'MASTER_PORT':'65536'},{'MASTER_HOST':'127.0.0.1 & command'}]:
            with self.assertRaises(ValueError):network_settings(environment,'master')
        for value in ['file:///a','http://user:secret@host','http://host?query=a']:
            with self.assertRaises(ValueError):validate_url(value)

    def test_component_commands_are_repository_relative(self):
        for component in ['master','worker','frontend']:
            command,cwd=command_for(component,{})
            self.assertTrue(cwd.is_relative_to(ROOT))
            self.assertNotIn('daliy',' '.join(command).replace(str(ROOT),''))
        command,_=command_for('master',{'MASTER_HOST':'0.0.0.0','MASTER_PORT':'8010'})
        self.assertEqual(command[-4:],['--host','0.0.0.0','--port','8010'])

    def test_examples_and_package_scripts_exist(self):
        for component in ['master','worker','frontend']:
            self.assertTrue((ROOT/component/'.env.example').is_file())
        scripts=json.loads((ROOT/'frontend/package.json').read_text())['scripts']
        self.assertTrue({'dev','build','test'}.issubset(scripts))

    def test_complete_verification_contains_all_required_stages(self):
        names={name for name,_,_ in stages()}
        self.assertTrue({'master','worker','benchmark','frontend','build','integration_setup',
            'master_dependencies','worker_dependencies','master_config','worker_config','frontend_config'}.issubset(names))

    def test_cmd_wrappers_preserve_working_directory_and_exit_status(self):
        for name in ['start_master','start_worker','start_frontend','test_all','benchmark_prepare','benchmark_report']:
            text=(ROOT/'scripts'/f'{name}.cmd').read_text()
            self.assertIn('pushd "%~dp0.."',text)
            self.assertIn('popd',text)
            self.assertIn('exit /b %taskExit%',text)
            self.assertNotIn('netsh',text.lower())
