import asyncio
from pathlib import Path

from cliping_bot.config import Settings
from cliping_bot.const import StorageMode
from cliping_bot.services.preferences import PreferencesStore
from cliping_bot.services.storage import LocalStorageManager


def test_local_storage_allocate_and_cleanup(tmp_path):
    settings = Settings()
    settings.local_output_dir = str(tmp_path / "local")
    settings.external_volume_path = None
    settings.use_ramdisk = False
    settings.local_delete_on_complete = True
    manager = LocalStorageManager(settings)

    allocation = asyncio.run(manager.allocate("job-local"))
    assert allocation.base_path is not None
    assert allocation.base_path.exists()
    assert allocation.warnings == []

    asyncio.run(manager.cleanup("job-local"))
    assert not allocation.base_path.exists()


def test_local_storage_warns_when_external_missing(tmp_path):
    settings = Settings()
    settings.local_output_dir = str(tmp_path / "fallback")
    settings.external_volume_path = str(tmp_path / "missing-volume")
    settings.use_ramdisk = False
    manager = LocalStorageManager(settings)

    allocation = asyncio.run(manager.allocate("job-warn"))
    assert allocation.base_path is not None
    assert allocation.base_path.parent == Path(settings.local_output_dir).expanduser()
    assert allocation.warnings  # fallback message present


def test_preferences_store_persists(tmp_path):
    prefs_path = tmp_path / "prefs.json"
    store = PreferencesStore(prefs_path)
    asyncio.run(store.set_storage_mode(123, StorageMode.CLOUD))

    prefs = asyncio.run(store.get(123, StorageMode.LOCAL))
    assert prefs.storage_mode is StorageMode.CLOUD

    # Recharger pour vérifier la persistance disque
    store_reloaded = PreferencesStore(prefs_path)
    prefs_reloaded = asyncio.run(store_reloaded.get(123, StorageMode.LOCAL))
    assert prefs_reloaded.storage_mode is StorageMode.CLOUD
