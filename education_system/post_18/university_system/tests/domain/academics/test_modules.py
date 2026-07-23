"""
Comprehensive tests for modules.py

Tests module definitions and data structures
"""

import pytest
from education_system.post_18.university_system.modules.domain.academics.services import modules


class TestModuleDefinitions:
    """Test suite for module definitions"""

    def test_compulsory_module_1_exists(self):
        """Test compulsory_module_1 is defined"""
        assert hasattr(modules, 'compulsory_module_1')
        assert isinstance(modules.compulsory_module_1, dict)

    def test_compulsory_module_1_structure(self):
        """Test compulsory_module_1 has correct structure"""
        module = modules.compulsory_module_1

        assert 'code' in module
        assert 'name' in module
        assert module['code'] == 'CIS0001'
        assert module['name'] == 'python programming'

    def test_compulsory_module_2_exists(self):
        """Test compulsory_module_2 is defined"""
        assert hasattr(modules, 'compulsory_module_2')
        assert isinstance(modules.compulsory_module_2, dict)

    def test_compulsory_module_2_structure(self):
        """Test compulsory_module_2 has correct structure"""
        module = modules.compulsory_module_2

        assert 'code' in module
        assert 'name' in module
        assert module['code'] == 'CIS0002'
        assert module['name'] == 'data structures and algorithms'

    def test_optional_module_1_exists(self):
        """Test optional_module_1 is defined"""
        assert hasattr(modules, 'optional_module_1')
        assert isinstance(modules.optional_module_1, dict)

    def test_optional_module_1_structure(self):
        """Test optional_module_1 has correct structure"""
        module = modules.optional_module_1

        assert 'code' in module
        assert 'name' in module
        assert module['code'] == 'CIS1001'
        assert module['name'] == 'Computational Thinking'

    def test_optional_module_2_structure(self):
        """Test optional_module_2 structure"""
        module = modules.optional_module_2

        assert module['code'] == 'CIS1002'
        assert module['name'] == 'Design Patterns'

    def test_optional_module_3_structure(self):
        """Test optional_module_3 structure"""
        module = modules.optional_module_3

        assert module['code'] == 'CIS1003'
        assert module['name'] == 'Test Driven Development'

    def test_optional_module_4_structure(self):
        """Test optional_module_4 structure"""
        module = modules.optional_module_4

        assert module['code'] == 'CIS1004'
        assert module['name'] == 'SQL Relational Database'

    def test_cs_optional_module_1_exists(self):
        """Test CS_optional_module_1 is defined"""
        assert hasattr(modules, 'CS_optional_module_1')
        assert isinstance(modules.CS_optional_module_1, dict)

    def test_cs_optional_module_1_structure(self):
        """Test CS_optional_module_1 has correct structure"""
        module = modules.CS_optional_module_1

        assert 'code' in module
        assert 'name' in module
        assert module['code'] == 'CIS2001'
        assert module['name'] == 'software quality assurance principles'

    def test_cs_optional_module_2_structure(self):
        """Test CS_optional_module_2 structure"""
        module = modules.CS_optional_module_2

        assert module['code'] == 'CIS2002'
        assert module['name'] == 'software reliabilities'

    def test_cs_optional_module_3_structure(self):
        """Test CS_optional_module_3 structure"""
        module = modules.CS_optional_module_3

        assert module['code'] == 'CIS2003'
        assert module['name'] == 'formal methods for system verifications'

    def test_cs_optional_module_4_structure(self):
        """Test CS_optional_module_4 structure"""
        module = modules.CS_optional_module_4

        assert module['code'] == 'CIS2004'
        assert module['name'] == 'algorithm complexity'

    def test_ds_optional_module_1_exists(self):
        """Test DS_optional_module_1 is defined"""
        assert hasattr(modules, 'DS_optional_module_1')
        assert isinstance(modules.DS_optional_module_1, dict)

    def test_ds_optional_module_1_structure(self):
        """Test DS_optional_module_1 has correct structure"""
        module = modules.DS_optional_module_1

        assert 'code' in module
        assert 'name' in module
        assert module['code'] == 'CIS3001'
        assert module['name'] == 'data visualisation'

    def test_ds_optional_module_2_structure(self):
        """Test DS_optional_module_2 structure"""
        module = modules.DS_optional_module_2

        assert module['code'] == 'CIS3002'
        assert module['name'] == 'an introduction to artificial intelligence in data science'

    def test_ds_optional_module_3_structure(self):
        """Test DS_optional_module_3 structure"""
        module = modules.DS_optional_module_3

        assert module['code'] == 'CIS3003'
        assert module['name'] == 'an introduction to machine learning'

    def test_ds_optional_module_4_structure(self):
        """Test DS_optional_module_4 structure"""
        module = modules.DS_optional_module_4

        assert module['code'] == 'CIS3004'
        assert module['name'] == 'statistical methods'


class TestModuleCodes:
    """Test module code uniqueness and format"""

    def test_all_module_codes_are_unique(self):
        """Test that all module codes are unique"""
        codes = [
            modules.compulsory_module_1['code'],
            modules.compulsory_module_2['code'],
            modules.optional_module_1['code'],
            modules.optional_module_2['code'],
            modules.optional_module_3['code'],
            modules.optional_module_4['code'],
            modules.CS_optional_module_1['code'],
            modules.CS_optional_module_2['code'],
            modules.CS_optional_module_3['code'],
            modules.CS_optional_module_4['code'],
            modules.DS_optional_module_1['code'],
            modules.DS_optional_module_2['code'],
            modules.DS_optional_module_3['code'],
            modules.DS_optional_module_4['code'],
        ]

        # Check all codes are unique
        assert len(codes) == len(set(codes)), "Duplicate module codes found"

    def test_compulsory_modules_use_cis0_prefix(self):
        """Test compulsory modules use CIS0xxx format"""
        assert modules.compulsory_module_1['code'].startswith('CIS0')
        assert modules.compulsory_module_2['code'].startswith('CIS0')

    def test_optional_modules_use_cis1_prefix(self):
        """Test optional modules use CIS1xxx format"""
        assert modules.optional_module_1['code'].startswith('CIS1')
        assert modules.optional_module_2['code'].startswith('CIS1')
        assert modules.optional_module_3['code'].startswith('CIS1')
        assert modules.optional_module_4['code'].startswith('CIS1')

    def test_cs_optional_modules_use_cis2_prefix(self):
        """Test CS optional modules use CIS2xxx format"""
        assert modules.CS_optional_module_1['code'].startswith('CIS2')
        assert modules.CS_optional_module_2['code'].startswith('CIS2')
        assert modules.CS_optional_module_3['code'].startswith('CIS2')
        assert modules.CS_optional_module_4['code'].startswith('CIS2')

    def test_ds_optional_modules_use_cis3_prefix(self):
        """Test DS optional modules use CIS3xxx format"""
        assert modules.DS_optional_module_1['code'].startswith('CIS3')
        assert modules.DS_optional_module_2['code'].startswith('CIS3')
        assert modules.DS_optional_module_3['code'].startswith('CIS3')
        assert modules.DS_optional_module_4['code'].startswith('CIS3')


class TestModuleNames:
    """Test module name characteristics"""

    def test_all_modules_have_names(self):
        """Test that all modules have non-empty names"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        for module in all_modules:
            assert 'name' in module
            assert module['name']
            assert len(module['name']) > 0

    def test_all_module_names_are_strings(self):
        """Test that all module names are strings"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        for module in all_modules:
            assert isinstance(module['name'], str)


class TestModuleGroups:
    """Test module groupings"""

    def test_compulsory_modules_count(self):
        """Test there are 2 compulsory modules"""
        compulsory_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2
        ]

        assert len(compulsory_modules) == 2

    def test_optional_modules_count(self):
        """Test there are 4 optional modules"""
        optional_modules = [
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4
        ]

        assert len(optional_modules) == 4

    def test_cs_optional_modules_count(self):
        """Test there are 4 CS optional modules"""
        cs_modules = [
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4
        ]

        assert len(cs_modules) == 4

    def test_ds_optional_modules_count(self):
        """Test there are 4 DS optional modules"""
        ds_modules = [
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4
        ]

        assert len(ds_modules) == 4

    def test_total_modules_count(self):
        """Test total number of modules"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        assert len(all_modules) == 14  # 2 compulsory + 4 optional + 4 CS + 4 DS


class TestModuleDataIntegrity:
    """Test module data integrity"""

    def test_modules_are_dictionaries(self):
        """Test all modules are dictionary objects"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        for module in all_modules:
            assert isinstance(module, dict)

    def test_modules_have_exactly_two_keys(self):
        """Test all modules have exactly 'code' and 'name' keys"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        for module in all_modules:
            assert set(module.keys()) == {'code', 'name'}

    def test_module_codes_are_strings(self):
        """Test all module codes are strings"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        for module in all_modules:
            assert isinstance(module['code'], str)

    def test_module_codes_match_pattern(self):
        """Test module codes match CISxxxx pattern"""
        all_modules = [
            modules.compulsory_module_1,
            modules.compulsory_module_2,
            modules.optional_module_1,
            modules.optional_module_2,
            modules.optional_module_3,
            modules.optional_module_4,
            modules.CS_optional_module_1,
            modules.CS_optional_module_2,
            modules.CS_optional_module_3,
            modules.CS_optional_module_4,
            modules.DS_optional_module_1,
            modules.DS_optional_module_2,
            modules.DS_optional_module_3,
            modules.DS_optional_module_4,
        ]

        import re
        pattern = re.compile(r'^CIS\d{4}$')

        for module in all_modules:
            assert pattern.match(module['code']), f"Code {module['code']} doesn't match pattern"
