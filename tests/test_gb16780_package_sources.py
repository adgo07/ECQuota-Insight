"""Real signed-package provenance checks for the narrowly approved V1.2 reference."""
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uebench.domain.models import StandardDefinition
from uebench.infrastructure.packages import StandardPackageBuilder, StandardPackageError
from .test_engine import make_standard
from .test_packages import make_service

ROOT = Path(__file__).resolve().parents[1]


def cement_definition():
    return StandardDefinition.model_validate_json(
        (ROOT/'data/definitions/gb-16780-2021.json').read_text(encoding='utf-8'))


def signed_package(tmp_path, private_key, definition):
    # Ephemeral test signer. No product private key or distributed PDF involved.
    return StandardPackageBuilder(private_key).build(
        tmp_path/'cement-source-check.uebench', [definition],
        package_id='cement-source-check', data_version='2026.10', distribute_sources=False)


def test_verified_cement_technical_reference_previews_and_installs(tmp_path):
    private_key=Ed25519PrivateKey.generate()
    paths,database,standards,service=make_service(tmp_path,private_key)
    try:
        package=signed_package(tmp_path,private_key,cement_definition())
        report=service.preview(package)
        assert report.valid,report.errors
        assert report.manifest.source_policy=='provenance-only'
        assert service.install(package).standards_installed==1
        assert standards.get_published('gb-16780-2021').rule_revision==2
        assert not list(paths.root.rglob('*.pdf'))
    finally:database.dispose()


@pytest.mark.parametrize('mutation',[
    'hash','path','clause','page','table','note','missing_primary','other_standard',
    'old_revision','grinding_reference','forged_primary','duplicate_reference',
])
def test_signed_package_rejects_unapproved_or_misattributed_reference(tmp_path,mutation):
    private_key=Ed25519PrivateKey.generate()
    _,database,standards,service=make_service(tmp_path,private_key)
    definition=cement_definition()
    indicator=definition.products[0].indicators[0]
    auxiliary=next(ref for ref in indicator.source_references if ref.standard_number!=definition.number)
    if mutation=='hash':auxiliary.source_sha256='0'*64
    elif mutation=='path':auxiliary.source_file='../201908301101185798.pdf'
    elif mutation=='clause':auxiliary.clause='附录C.5(C.7)'
    elif mutation=='page':auxiliary.page=13
    elif mutation=='table':auxiliary.table='表1（2021正式版）'
    elif mutation=='note':auxiliary.note='2021现行标准公式'
    elif mutation=='missing_primary':indicator.source_references=[auxiliary]
    elif mutation=='other_standard':
        definition=make_standard()
        definition.products[0].indicators[0].source_references.append(auxiliary.model_copy(deep=True))
    elif mutation=='old_revision':definition.rule_revision=1
    elif mutation=='grinding_reference':definition.products[0].indicators[-1].source_references.append(auxiliary.model_copy(deep=True))
    elif mutation=='forged_primary':
        definition.source_sha256='0'*64
        for product in definition.products:
            for item in product.indicators:
                for reference in item.source_references:
                    if reference.standard_number==definition.number:reference.source_sha256='0'*64
    elif mutation=='duplicate_reference':indicator.source_references.append(auxiliary.model_copy(deep=True))
    try:
        package=signed_package(tmp_path,private_key,definition)
        # Valid Ed25519 signature and manifest hashes do not legitimize a
        # fabricated source, a reference-only draft as primary, or cross-use.
        report=service.preview(package)
        assert not report.valid
        assert any('来源' in error for error in report.errors),report.errors
        with pytest.raises(StandardPackageError):service.install(package)
        assert standards.list_all()==[]
        assert service.list_history()==[]
    finally:database.dispose()
