# test_Wirelessgopro.py/Open GoPro, Version 2.0 (C) Copyright 2021 GoPro, Inc. (http://Wirelessgopro.com/OpenGoPro).
# This copyright was auto-generated on Fri Sep 10 01:35:03 UTC 2021

# pylint: disable=redefined-outer-name


"""Unit testing of GoPro Client"""

import asyncio
from pathlib import Path
from typing import Any

import pytest
import requests
import requests_mock

from open_gopro import constants
from open_gopro.communicator_interface import HttpMessage
from open_gopro.constants import ErrorCode, QueryCmdId, SettingId, StatusId, settings
from open_gopro.constants.statuses import InternalBatteryBars
from open_gopro.exceptions import GoProNotOpened, ResponseTimeout
from open_gopro.gopro_wireless import WirelessGoPro
from open_gopro.models import GoProResp
from open_gopro.parser_interface import GlobalParsers
from open_gopro.types import UpdateType
from tests import mock_good_response
from tests.mocks import MockGoProMaintainBle


@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_lifecycle(mock_wireless_gopro: MockGoProMaintainBle):
    async def set_disconnect_event():
        mock_wireless_gopro._disconnect_handler(None)

    # We're not yet open so can't send commands
    assert not mock_wireless_gopro.is_open
    with pytest.raises(GoProNotOpened):
        await mock_wireless_gopro.ble_command.enable_wifi_ap(enable=False)

    # Mock ble / wifi open
    await mock_wireless_gopro.open()
    assert mock_wireless_gopro.is_open

    # Ensure we can't send commands because not ready
    assert not await mock_wireless_gopro.is_ready
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(mock_wireless_gopro.ble_command.enable_wifi_ap(enable=False), 1)

    # Mock receiving initial not-encoding and not-busy statuses
    await mock_wireless_gopro._update_internal_state(update=StatusId.ENCODING, value=False)
    await mock_wireless_gopro._update_internal_state(update=StatusId.BUSY, value=False)
    assert await mock_wireless_gopro.is_ready

    results = await asyncio.gather(
        mock_wireless_gopro.ble_command.enable_wifi_ap(enable=False),
        mock_wireless_gopro._sync_resp_ready_q.put(mock_good_response),
    )

    assert results[0].ok
    assert await mock_wireless_gopro.ble_command.get_open_gopro_api_version()

    # Ensure keep alive was received and is correct
    assert (await mock_wireless_gopro.generic_spy.get())[0] == 66

    # Mock closing
    asyncio.gather(mock_wireless_gopro.close(), set_disconnect_event())
    assert mock_wireless_gopro._keep_alive_task.cancelled


@pytest.mark.asyncio
async def test_gopro_open(mock_wireless_gopro_basic: WirelessGoPro):
    await mock_wireless_gopro_basic.open()
    assert mock_wireless_gopro_basic.is_ble_connected
    assert mock_wireless_gopro_basic.is_http_connected
    assert mock_wireless_gopro_basic.identifier == "scanned_device"


@pytest.mark.asyncio
async def test_http_get(mock_wireless_gopro_basic: WirelessGoPro, monkeypatch):
    message = HttpMessage("gopro/camera/stream/start", None)
    session = requests.Session()
    adapter = requests_mock.Adapter()
    session.mount(mock_wireless_gopro_basic._base_url + message._endpoint, adapter)
    adapter.register_uri("GET", mock_wireless_gopro_basic._base_url + message._endpoint, json="{}")
    monkeypatch.setattr("open_gopro.gopro_base.requests.get", session.get)
    response = await mock_wireless_gopro_basic._get_json(message)
    assert response.ok


@pytest.mark.asyncio
async def test_http_file(mock_wireless_gopro_basic: WirelessGoPro, monkeypatch):
    message = HttpMessage("videos/DCIM/100GOPRO/dummy.MP4", None)
    out_file = Path("test.mp4")
    session = requests.Session()
    adapter = requests_mock.Adapter()
    session.mount(mock_wireless_gopro_basic._base_url + message._endpoint, adapter)
    adapter.register_uri("GET", mock_wireless_gopro_basic._base_url + message._endpoint, text="BINARY DATA")
    monkeypatch.setattr("open_gopro.gopro_base.requests.get", session.get)
    await mock_wireless_gopro_basic._get_stream(message, camera_file=out_file, local_file=out_file)
    assert out_file.exists()


@pytest.mark.asyncio
async def test_http_response_timeout(mock_wireless_gopro_basic: WirelessGoPro, monkeypatch):
    with pytest.raises(ResponseTimeout):
        message = HttpMessage("gopro/camera/stream/start", None)
        session = requests.Session()
        adapter = requests_mock.Adapter()
        session.mount(mock_wireless_gopro_basic._base_url + message._endpoint, adapter)
        adapter.register_uri(
            "GET", mock_wireless_gopro_basic._base_url + message._endpoint, exc=requests.exceptions.ConnectTimeout
        )
        monkeypatch.setattr("open_gopro.gopro_base.requests.get", session.get)
        await mock_wireless_gopro_basic._get_json(message, timeout=1)


@pytest.mark.asyncio
async def test_http_response_error(mock_wireless_gopro_basic: WirelessGoPro, monkeypatch):
    message = HttpMessage("gopro/camera/stream/start", None)
    session = requests.Session()
    adapter = requests_mock.Adapter()
    session.mount(mock_wireless_gopro_basic._base_url + message._endpoint, adapter)
    adapter.register_uri(
        "GET",
        mock_wireless_gopro_basic._base_url + message._endpoint,
        status_code=403,
        reason="something bad happened",
        json="{}",
    )
    monkeypatch.setattr("open_gopro.gopro_base.requests.get", session.get)
    response = await mock_wireless_gopro_basic._get_json(message)
    assert not response.ok


@pytest.mark.asyncio
async def test_get_update(mock_wireless_gopro_basic: WirelessGoPro):
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()
    event = asyncio.Event()

    async def receive_encoding_status(id: UpdateType, value: bool):
        event.set()

    mock_wireless_gopro_basic.register_update(receive_encoding_status, StatusId.ENCODING)
    not_encoding = bytearray([0x05, 0x93, 0x00, StatusId.ENCODING.value, 0x01, 0x00])
    mock_wireless_gopro_basic._notification_handler(0xFF, not_encoding)
    await event.wait()

    # Now ensure unregistering works
    event.clear()
    mock_wireless_gopro_basic.unregister_update(receive_encoding_status, StatusId.ENCODING)
    not_encoding = bytearray([0x05, 0x13, 0x00, StatusId.ENCODING.value, 0x01, 0x00])
    mock_wireless_gopro_basic._notification_handler(0xFF, not_encoding)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), 1)


@pytest.mark.asyncio
async def test_route_all_data(mock_wireless_gopro_basic: WirelessGoPro):
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    # GIVEN
    mock_data = {"one": 1, "two": 2}
    mock_response = GoProResp(
        protocol=GoProResp.Protocol.BLE,
        status=ErrorCode.SUCCESS,
        data=mock_data,
        identifier=QueryCmdId.GET_SETTING_VAL,
    )

    # WHEN
    # Make it appear to be the synchronous response
    await mock_wireless_gopro_basic._sync_resp_wait_q.put(mock_response)
    # Route the mock response
    await mock_wireless_gopro_basic._route_response(mock_response)
    # Get the routed response
    routed_response = await mock_wireless_gopro_basic._sync_resp_ready_q.get()

    # THEN
    assert routed_response.data == mock_data


@pytest.mark.asyncio
async def test_route_individual_data(mock_wireless_gopro_basic: WirelessGoPro):
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    # GIVEN
    mock_data = {"one": 1}
    mock_response = GoProResp(
        protocol=GoProResp.Protocol.BLE,
        status=ErrorCode.SUCCESS,
        data=mock_data,
        identifier=QueryCmdId.GET_SETTING_VAL,
    )

    # WHEN
    # Make it appear to be the synchronous response
    await mock_wireless_gopro_basic._sync_resp_wait_q.put(mock_response)
    # Route the mock response
    await mock_wireless_gopro_basic._route_response(mock_response)
    # Get the routed response
    routed_response = await mock_wireless_gopro_basic._sync_resp_ready_q.get()

    # THEN
    assert routed_response.data == 1


@pytest.mark.asyncio
async def test_get_update_unregister(mock_wireless_gopro_basic: WirelessGoPro):
    event = asyncio.Event()
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    async def receive_encoding_status(id: UpdateType, value: bool):
        event.set()

    mock_wireless_gopro_basic.register_update(receive_encoding_status, StatusId.ENCODING)
    not_encoding = bytearray([0x05, 0x93, 0x00, StatusId.ENCODING.value, 0x01, 0x00])
    mock_wireless_gopro_basic._notification_handler(0xFF, not_encoding)
    await event.wait()

    # Now ensure unregistering works
    event.clear()
    mock_wireless_gopro_basic.unregister_update(receive_encoding_status)
    not_encoding = bytearray([0x05, 0x13, 0x00, StatusId.ENCODING.value, 0x01, 0x00])
    mock_wireless_gopro_basic._notification_handler(0xFF, not_encoding)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(event.wait(), 1)


def test_get_param_values_by_id():
    vector = list(settings.VideoResolution)[0]
    assert GlobalParsers.get_query_container(SettingId.VIDEO_RESOLUTION)(vector.value) == vector


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_register_all_unregister_all_statuses(mock_wireless_gopro_basic: WirelessGoPro):
    # GIVEN
    status_q: asyncio.Queue[tuple[UpdateType, InternalBatteryBars]] = asyncio.Queue()
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    async def status_handler(update: UpdateType, value: InternalBatteryBars) -> None:
        await status_q.put((update, value))

    # WHEN
    await mock_wireless_gopro_basic.ble_command.register_for_all_statuses(callback=status_handler)
    battery_bars_0 = bytearray([0x05, 0x93, 0x00, StatusId.INTERNAL_BATTERY_BARS.value, 0x01, 0x00])
    mock_wireless_gopro_basic._notification_handler(0xFF, battery_bars_0)

    # THEN
    status, value = await status_q.get()
    assert status == StatusId.INTERNAL_BATTERY_BARS
    assert value == InternalBatteryBars.ZERO

    # WHEN
    await mock_wireless_gopro_basic.ble_command.unregister_for_all_statuses(callback=status_handler)
    battery_bars_1 = bytearray([0x05, 0x93, 0x00, StatusId.INTERNAL_BATTERY_BARS.value, 0x01, 0x01])
    mock_wireless_gopro_basic._notification_handler(0xFF, battery_bars_1)

    # THEN
    with pytest.raises(asyncio.TimeoutError):
        value = await asyncio.wait_for(status_q.get(), 1)
        print(value)


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_register_all_unregister_all_settings(mock_wireless_gopro_basic: WirelessGoPro):
    # GIVEN
    setting_q: asyncio.Queue[tuple[UpdateType, InternalBatteryBars]] = asyncio.Queue()
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    async def setting_handler(update: UpdateType, value: InternalBatteryBars) -> None:
        await setting_q.put((update, value))

    # WHEN
    await mock_wireless_gopro_basic.ble_command.register_for_all_settings(callback=setting_handler)
    resolution_update = bytearray(
        [0x05, 0x92, 0x00, SettingId.VIDEO_RESOLUTION.value, 0x01, constants.settings.VideoResolution.NUM_1080]
    )
    mock_wireless_gopro_basic._notification_handler(0xFF, resolution_update)

    # THEN
    setting, value = await setting_q.get()
    assert setting == SettingId.VIDEO_RESOLUTION
    assert value == constants.settings.VideoResolution.NUM_1080

    # WHEN
    await mock_wireless_gopro_basic.ble_command.unregister_for_all_settings(callback=setting_handler)
    resolution_update_2 = bytearray(
        [0x05, 0x93, 0x00, StatusId.INTERNAL_BATTERY_BARS.value, 0x01, constants.settings.VideoResolution.NUM_1440]
    )
    mock_wireless_gopro_basic._notification_handler(0xFF, resolution_update_2)

    # THEN
    with pytest.raises(asyncio.TimeoutError):
        value = await asyncio.wait_for(setting_q.get(), 1)
        print(value)


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_register_all_unregister_one_settings(mock_wireless_gopro_basic: WirelessGoPro):
    # GIVEN
    setting_q: asyncio.Queue[tuple[UpdateType, InternalBatteryBars]] = asyncio.Queue()
    mock_wireless_gopro_basic._loop = asyncio.get_running_loop()

    async def setting_handler(update: UpdateType, value: InternalBatteryBars) -> None:
        await setting_q.put((update, value))

    # WHEN
    await mock_wireless_gopro_basic.ble_command.register_for_all_settings(callback=setting_handler)
    resolution_update = bytearray(
        [0x05, 0x92, 0x00, SettingId.VIDEO_RESOLUTION.value, 0x01, constants.settings.VideoResolution.NUM_1080]
    )
    mock_wireless_gopro_basic._notification_handler(0xFF, resolution_update)

    # THEN
    setting, value = await setting_q.get()
    assert setting == SettingId.VIDEO_RESOLUTION
    assert value == constants.settings.VideoResolution.NUM_1080

    # WHEN
    await mock_wireless_gopro_basic.ble_setting.video_resolution.unregister_value_update(callback=setting_handler)
    resolution_update_2 = bytearray(
        [0x05, 0x93, 0x00, StatusId.INTERNAL_BATTERY_BARS.value, 0x01, constants.settings.VideoResolution.NUM_1440]
    )
    mock_wireless_gopro_basic._notification_handler(0xFF, resolution_update_2)

    # THEN
    with pytest.raises(asyncio.TimeoutError):
        value = await asyncio.wait_for(setting_q.get(), 1)
        print(value)
