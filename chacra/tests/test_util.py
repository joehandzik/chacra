import os
import random
import string
import pytest
import pecan
from chacra import util
from chacra import models


source_rpms = [
    "%s-%s.src.rpm" % (
        ''.join(random.choice(string.ascii_letters) for _ in range(10)),
        '.'.join(random.choice(string.digits) for _ in range(3))
    ) for i in range(10)
] + [
    'ceph-deploy.SRC.rpm',
]

x64_rpms = [
    "%s-%s.x86_64.rpm" % (
        ''.join(random.choice(string.ascii_letters) for _ in range(10)),
        '.'.join(random.choice(string.digits) for _ in range(3))
    ) for i in range(10)
] + [
    'ceph-deploy.X86_64.rpm',
]

noarch = [
    "%s-%s.noarch.rpm" % (
        ''.join(random.choice(string.ascii_letters) for _ in range(10)),
        '.'.join(random.choice(string.digits) for _ in range(3))
    ) for i in range(10)
] + [
    'somenoarch.rpm',
    'ceph-deploy-NOARCHY-.rpm'
]

undetermined = [
    'garbage.deb',
    'test.tar.gz',
    'removeme.txt'
]


class TestRepoDirectory(object):

    @pytest.mark.parametrize('binary', source_rpms)
    def test_source_rpm(self, binary):
        result = util.infer_arch_directory(binary)
        assert result == 'SRPMS'

    @pytest.mark.parametrize('binary', x64_rpms)
    def test_x64_rpm(self, binary):
        result = util.infer_arch_directory(binary)
        assert result == 'x86_64'

    @pytest.mark.parametrize('binary', noarch)
    def test_noarch(self, binary):
        result = util.infer_arch_directory(binary)
        assert result == 'noarch'

    @pytest.mark.parametrize('binary', undetermined)
    def test_undetermined(self, binary):
        result = util.infer_arch_directory(binary)
        assert result == 'noarch'


class TestRepoPaths(object):

    def setup(self):
        self.repo = models.Repo(
            models.Project('ceph-deploy'),
            'master',
            'centos',
            'el7'
        )

    def test_relative(self):
        pecan.conf.repos_root = '/tmp/repos'
        result = util.repo_paths(self.repo)
        assert result['relative'] == 'master/centos/el7'

    def test_root(self):
        pecan.conf.repos_root = '/tmp/repos'
        result = util.repo_paths(self.repo)
        assert result['root'] == '/tmp/repos/ceph-deploy'

    def test_absolute(self):
        pecan.conf.repos_root = '/tmp/repos'
        result = util.repo_paths(self.repo)['absolute']
        assert result == '/tmp/repos/ceph-deploy/master/centos/el7'


class TestMakeDirs(object):

    def test_path_exists(self, tmpdir):
        path = str(tmpdir)
        assert util.makedirs(path) is None

    def test_path_gets_created(self, tmpdir):
        path = os.path.join(str(tmpdir), 'createme')
        assert util.makedirs(path).endswith('/createme')


class TestGetExtraRepos(object):

    def test_no_repo_config(self):
        result = util.get_extra_repos('ceph', 'firefly')
        assert result == {}

    def test_fallback_to_all_repos(self):
        conf = {'ceph': {'all': {'ceph-deploy': ['all']}}}
        # master is not defined, so 'all' is used
        result = util.get_extra_repos('ceph', 'master',  repo_config=conf)
        assert result == {'ceph-deploy': ['all']}

    def test_fallback_to_all_repos_gets_empty_dict(self):
        conf = {'ceph': {'master': {'ceph-deploy': ['all']}}}
        # 'firefly' is not defined, so 'all' is attempted
        result = util.get_extra_repos('ceph', 'firefly',  repo_config=conf)
        assert result == {}

    def test_no_matching_project(self):
        conf = {'ceph': {'all': {'ceph-deploy': ['all']}}}
        result = util.get_extra_repos('ceph-deploy', 'master',  repo_config=conf)
        assert result == {}

    def test_matching_project_ref(self):
        conf = {'ceph': {'firefly': {'ceph-deploy': ['all']}}}
        result = util.get_extra_repos('ceph', 'firefly',  repo_config=conf)
        assert result == {'ceph-deploy': ['all']}

    def test_matching_ref_over_all(self):
        conf = {'ceph': {
            'all': {'ceph-deploy': ['master']},
            'firefly': {'ceph-deploy': ['all']}
            }
        }
        result = util.get_extra_repos('ceph', 'firefly',  repo_config=conf)
        assert result == {'ceph-deploy': ['master']}

    def test_matching_project_ref_and_all_refs(self):
        # all versions of ceph-deploy for this repo, and just the 'firefly'
        # release of ceph-release.
        conf = {
            'ceph': {
                'all': {
                    'ceph-deploy': ['all'],
                },
                'firefly': {
                    'ceph-release': ['firefly']
                    }
                }
            }
        result = util.get_extra_repos('ceph', 'firefly',  repo_config=conf)
        assert result == {'ceph-deploy': ['all'], 'ceph-release': ['firefly']}


class TestCombined(object):

    def test_no_repo_config(self):
        result = util.get_combined_repos('ceph')
        assert result == []

    def test_project_is_not_defined(self):
        conf = {'ceph': {'all': {'ceph-deploy': ['all']}}}
        result = util.get_combined_repos('ceph-deploy', repo_config=conf)
        assert result == []

    def test_combined_is_not_defined_in_project(self):
        conf = {'ceph': {'all': {'ceph-deploy': ['all']}}}
        result = util.get_combined_repos('ceph', repo_config=conf)
        assert result == []

    def test_combined_is_defined_and_found(self):
        conf = {'ceph': {'combined': ['wheezy']}}
        result = util.get_combined_repos('ceph', repo_config=conf)
        assert result == ['wheezy']


class TestGetBinaries(object):

    def setup(self):
        self.p = models.Project('ceph')

    def test_no_project(self, session):
        result = util.get_extra_binaries('f', 'ubuntu', 'precise')
        assert result == []

    def test_no_matching_ref_without_specific_ref(self, session):
        models.commit()
        result = util.get_extra_binaries('ceph', 'ubuntu', 'precise')
        assert result == []

    def test_no_matching_ref_with_specific_ref(self, session):
        models.commit()
        result = util.get_extra_binaries(
            'ceph', 'ubuntu', 'precise', ref='master')
        assert result == []

    def test_no_ref_matches_binaries(self, session):
        models.Binary(
            'ceph-1.1.deb',
            self.p,
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        models.Binary(
            'ceph-1.0.deb',
            self.p,
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )

        models.commit()
        result = util.get_extra_binaries('ceph', 'ubuntu', 'trusty')
        assert len(result) == 2

    def test_ref_matches_binaries(self, session):
        models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        models.Binary(
            'ceph-1.0.deb',
            self.p,
            ref='master',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )

        models.commit()
        result = util.get_extra_binaries('ceph', 'ubuntu', 'trusty', ref='master')
        assert len(result) == 1

    def test_ref_matches_binaries_from_distro_versions(self, session):
        models.Binary(
            'ceph-1.0.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='precise',
            arch='all',
            )
        models.Binary(
            'ceph-1.0.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )

        models.commit()
        result = util.get_extra_binaries(
            'ceph',
            'ubuntu',
            'trusty',
            distro_versions=['precise', 'trusty'],
            ref='firefly')
        assert len(result) == 2


class TestRepreproCommand(object):

    def setup(self):
        self.p = models.Project('ceph')

    def test_deb_binary(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        command = util.reprepro_command('/path', binary)
        assert command[-3] == 'includedeb'

    def test_deb_dsc(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.dsc',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        command = util.reprepro_command('/path', binary)
        assert command[-3] == 'includedsc'

    def test_deb_changes(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.changes',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        command = util.reprepro_command('/path', binary)
        assert command[-3] == 'include'


class TestRepreproCommands(object):

    def setup(self):
        self.p = models.Project('ceph')

    def test_no_distro_versions_binary_non_generic(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        commands = util.reprepro_commands('/path', binary)
        command = commands[0]
        assert len(commands) == 1
        assert 'trusty' in command

    def test_multiple_distro_versions_non_generic(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='trusty',
            arch='all',
            )
        commands = util.reprepro_commands(
            '/path',
            binary,
            distro_versions= ['precise', 'trusty', 'wheezy'])
        command = commands[0]
        assert len(commands) == 1
        assert 'trusty' in command

    def test_no_distro_versions_binary_no_fallback_generic(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='generic',
            arch='all',
            )
        commands = util.reprepro_commands('/path', binary)
        assert commands == []

    def test_no_distro_versions_binary_with_fallback_generic(self, session, tmpdir):
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='generic',
            arch='all',
            )
        commands = util.reprepro_commands('/path', binary, fallback_version='jessie')
        command = commands[0]
        assert len(commands) == 1
        assert 'jessie' in command

    def test_distro_versions_binary_with_fallback_generic(self, session, tmpdir):
        distro_versions = ['trusty', 'wheezy', 'precise']
        pecan.conf.distributions_root = str(tmpdir)
        binary = models.Binary(
            'ceph-1.1.deb',
            self.p,
            ref='firefly',
            distro='ubuntu',
            distro_version='generic',
            arch='all',
            )
        commands = util.reprepro_commands(
            '/path',
            binary,
            distro_versions=distro_versions,
            fallback_version='jessie'
        )
        assert len(commands) == 3
        # this is a poor use of assert here, but we are trying to ensure that
        # all distro_versions were used correctly, if something fails here it
        # means that they didn't get added to the reprepro command
        for c in commands:
            assert c[-2] in distro_versions

class TestGetDistributionsFileContext(object):

    def setup(self):
        self.distro_conf = {
            "defaults": {
                "foo": "bar",
                "bar": "baz",
            },
            "ceph": {
                "name": "ceph",
            },
        }
        pecan.conf.distributions = self.distro_conf

    def test_top_level_keys_exist(self, session):
        result = util.get_distributions_file_context("ceph")
        assert "data" in result
        assert "distributions" in result

    def test_field_addition(self, session):
        result = util.get_distributions_file_context("ceph")
        assert "name" in result["data"]
        assert result["data"]["name"] == "ceph"

    def test_project_doesnt_exist(self, session):
        result = util.get_distributions_file_context("ceph-deploy")
        assert len(result["data"]) == 2
        assert "foo" in result["data"]
        assert "bar" in result["data"]

    def test_adds_new_field(self, session):
        self.distro_conf["ceph"]["test"] = "foo"
        pecan.conf.distributions = self.distro_conf
        result = util.get_distributions_file_context("ceph")
        assert "test" in result["data"]
        assert result['data']['test'] == "foo"

    def test_field_override(self, session):
        self.distro_conf["ceph"]["foo"] = "blarg"
        pecan.conf.distributions = self.distro_conf
        result = util.get_distributions_file_context("ceph")
        assert "foo" in result["data"]
        assert result['data']['foo'] == "blarg"
