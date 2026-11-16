"""New API modules must explicitly declare their commercial capability policy."""
import ast
from pathlib import Path

import pytest

from app.feature_catalog import BUILT
from app.services.feature_policy import PERMISSION_FEATURES, features_for_permission


def test_every_route_permission_has_a_declared_feature_policy():
    root = Path(__file__).resolve().parents[1] / 'app'
    permissions = set()
    for source in root.rglob('*.py'):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'require_permission':
                if node.args and isinstance(node.args[0], ast.Constant):
                    permissions.add(node.args[0].value)
    assert permissions
    for permission in permissions:
        assert isinstance(features_for_permission(permission), tuple), permission
    assert all(feature in BUILT for features in PERMISSION_FEATURES.values() for feature in features)


def test_new_permission_namespace_fails_closed_and_specific_subfeatures_win():
    with pytest.raises(ValueError):
        features_for_permission('unreviewed_module.view')
    assert features_for_permission('staff.hr.manage') == ('staff', 'staff_hr')
    assert features_for_permission('staff.roster.manage') == ('staff', 'staff_hr', 'staff_roster')
