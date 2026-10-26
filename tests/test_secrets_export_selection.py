"""Explicit secret selections only; every key, picker and GPG call is synthetic."""

import shlex
import tarfile
import unittest

import test_secrets_export

KEY_ONE = 'fixture-one@example.invalid|0123456789ABCDEF'
KEY_TWO = 'fixture-two@example.invalid|FEDCBA9876543210'


class ExportSelection(unittest.TestCase):
    setUp = test_secrets_export.SecretsExport.setUp
    run_bash = test_secrets_export.SecretsExport.run_bash

    def export(self, gpg_marks=0, gpg_selection=KEY_ONE, ssh_marks=0,
               candidates=KEY_ONE + '\n' + KEY_TWO, picker_error=0):
        # Simulate fzf's Enter action using the actual configured transform.
        # A focused row exists even when zero items were explicitly marked.
        return self.run_bash(f'''
check_deps() {{ :; }}
list_gpg_keys() {{ printf '%s\\n' {shlex.quote(candidates)}; }}
list_ssh_config_hosts() {{ printf '%s\\n' fixture.example; }}
list_sparrow_wallets() {{ printf '%s\\n' fixture-wallet; }}
get_identity_file_for_host() {{ :; }}
extract_ssh_config_host() {{ printf 'Host fixture.example\\n HostName 192.0.2.1\\n'; }}
list_removable_media() {{ printf 'called\\n' > media-called; }}
FZF_DEFAULT_OPTS='--select-1 --bind enter:select-all+accept'
FZF_DEFAULT_OPTS_FILE=/not-a-real-personal-fzf-file
export FZF_DEFAULT_OPTS FZF_DEFAULT_OPTS_FILE
fzf() {{
    [[ $FZF_DEFAULT_OPTS == '' && $FZF_DEFAULT_OPTS_FILE == /dev/null ]] || return 97
    local binding='' header='' action count=0 selected=''
    cat >/dev/null
    while (($#)); do
        case $1 in
            --bind) binding=$2; shift 2 ;;
            --header=*) header=${{1#--header=}}; shift ;;
            *) shift ;;
        esac
    done
    case $header in
        'GPG Secret Keys'*) count={gpg_marks}; selected={shlex.quote(gpg_selection)} ;;
        'SSH Hosts'*) count={ssh_marks}; selected=fixture.example ;;
    esac
    [[ {picker_error} == 0 ]] || {{ printf '%s\\n' "$selected"; return {picker_error}; }}
    [[ $binding == enter:transform:* ]] || return 97
    action=$(FZF_SELECT_COUNT=$count /bin/sh -c "${{binding#enter:transform:}}") || return 97
    [[ $action == accept ]] || return 130
    printf '%s\\n' "$selected"
}}
gpg() {{
    printf '%s\\n' "$*" >> gpg-calls
    if [[ $1 == --export-secret-keys ]]; then
        [[ $# == 3 && -n $3 ]] || return 97
        printf 'SYNTHETIC SECRET KEY\\n'
    elif [[ $1 == --symmetric ]]; then
        cat > "${{@: -1}}"
    else
        return 97
    fi
}}
main
''')

    def test_enter_with_no_marked_items_exports_nothing_despite_focused_rows(self):
        result = self.export()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Nothing selected', result.stderr)
        self.assertFalse((self.base / 'gpg-calls').exists())
        self.assertFalse((self.base / 'media-called').exists())
        self.assertEqual([], list(self.base.glob('secrets-*')))
        self.assertEqual([], list(self.base.glob('tmp.*')))

    def test_only_explicitly_marked_gpg_key_is_exported(self):
        result = self.export(gpg_marks=1)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        calls = (self.base / 'gpg-calls').read_text().splitlines()
        self.assertEqual(['--export-secret-keys --armor 0123456789ABCDEF'],
                         [call for call in calls if call.startswith('--export-secret-keys')])
        with tarfile.open(next(self.base.glob('secrets-*.tar.gz.gpg'))) as archive:
            self.assertIn('./gpg_0123456789ABCDEF.asc', archive.getnames())
            self.assertNotIn('./gpg_FEDCBA9876543210.asc', archive.getnames())

    def test_skipping_gpg_while_selecting_ssh_never_exports_a_gpg_key(self):
        result = self.export(ssh_marks=1)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn('--export-secret-keys', (self.base / 'gpg-calls').read_text())
        with tarfile.open(next(self.base.glob('secrets-*.tar.gz.gpg'))) as archive:
            self.assertIn('./ssh_config', archive.getnames())
            self.assertFalse(any(name.startswith('./gpg_') for name in archive.getnames()))

    def test_empty_malformed_and_option_like_key_ids_fail_before_gpg(self):
        for record in ('fixture@example.invalid|', 'no-delimiter',
                       'fixture@example.invalid|--export-all', 'fixture@example.invalid|*'):
            with self.subTest(record=record):
                result = self.export(gpg_marks=1, gpg_selection=record, candidates=record)
                self.assertNotEqual(0, result.returncode)
                self.assertIn('selected GPG key', result.stderr)
                self.assertFalse((self.base / 'gpg-calls').exists())
                self.assertEqual([], list(self.base.glob('secrets-*')))

    def test_picker_errors_and_forged_selections_are_not_accepted(self):
        for selection, error in ((KEY_ONE, 2), ('forged@example.invalid|AAAAAAAAAAAAAAAA', 0)):
            result = self.export(gpg_marks=1, gpg_selection=selection, picker_error=error)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('Could not select GPG keys safely', result.stderr)
            self.assertFalse((self.base / 'gpg-calls').exists())
