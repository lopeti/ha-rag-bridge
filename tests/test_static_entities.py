import pytest

from custom_components.ha_rag_expose_api import http
from custom_components.ha_rag_expose_api.http import StaticEntitiesView


class FakeReq:
    def __init__(self, hass):
        self.app = {"hass": hass}


class FakeModule:
    def __init__(self, reg):
        self._reg = reg

    def async_get(self, hass):
        return self._reg


class Area:
    def __init__(self, id, name, floor=None, aliases=None):
        self.id = id
        self.name = name
        self.floor = floor
        self.aliases = aliases or []


class Device:
    def __init__(self, id, name, model, manufacturer, area_id=None):
        self.id = id
        self.name = name
        self.model = model
        self.manufacturer = manufacturer
        self.area_id = area_id


class Entity:
    def __init__(
        self,
        entity_id,
        platform,
        device_id=None,
        area_id=None,
        domain=None,
        original_name=None,
    ):
        self.entity_id = entity_id
        self.platform = platform
        self.device_id = device_id
        self.area_id = area_id
        self.domain = domain
        self.original_name = original_name


class FakeAreaReg:
    def __init__(self, areas):
        self._areas = {a.id: a for a in areas}

    def async_list_areas(self):
        return list(self._areas.values())


class FakeDeviceReg:
    def __init__(self, devices):
        self.devices = {d.id: d for d in devices}


class FakeEntityReg:
    def __init__(self, entities):
        self.entities = {e.entity_id: e for e in entities}


@pytest.mark.asyncio
async def test_static_entities(monkeypatch):
    areas = [
        Area("a1", "Kitchen", "f1", ["kitchen"]),
        Area("a2", "Living", "f1"),
        Area("a3", "Hall"),
    ]
    area_reg = FakeAreaReg(areas)
    device = Device("d1", "Lamp", "L1", "Acme", area_id="a1")
    dev_reg = FakeDeviceReg([device])
    ent1 = Entity(
        "light.lamp",
        "light",
        device_id="d1",
        area_id="a1",
        domain="light",
        original_name="Lamp",
    )
    ent2 = Entity(
        "sensor.temp", "sensor", area_id="a2", domain="sensor", original_name="Temp"
    )
    ent_reg = FakeEntityReg([ent1, ent2])

    monkeypatch.setattr(
        http,
        "_helpers",
        (FakeModule(area_reg), FakeModule(dev_reg), FakeModule(ent_reg)),
    )

    hass = object()
    res = await StaticEntitiesView().get(FakeReq(hass))

    assert len(res["areas"]) == 3
    assert len(res["devices"]) == 1
    assert len(res["entities"]) == 2
