from dataclasses import dataclass
from typing import Union, List
from pydantic import BaseModel


class IoTFeatureValue(BaseModel, extra="allow"):
    type: str
    value: Union[int, float]
    unit: str


class IotFeatureProperties(BaseModel, extra="allow"):
    value: IoTFeatureValue


class IoTFeature(BaseModel, extra="allow"):
    feature: str
    properties: IotFeatureProperties


class IoTFeatureResponse(BaseModel):
    data: List[IoTFeature]


@dataclass
class PhotovoltaicData:
    _solar_power: float
    _battery_power: float
    _grid_exchange: float
    _state_of_charge: int
    _household: float

    @property
    def solar_power(self) -> float:
        """Current solar production in Watt (-> photovoltaic.production.current)"""
        return self._solar_power

    @property
    def battery_power(self) -> float:
        """Current battery power. Positive when discharging, negative when charging (-> ess.power)"""
        return self._battery_power

    @property
    def state_of_charge(self) -> int:
        """Current battery charge state in percent (-> ess.stateOfCharge)"""
        return self._state_of_charge

    @property
    def grid_exchange(self) -> float:
        """Current grid power. Positive = 'Netzbezug', negative = 'Einspeisung' (-> pcc.transfer.power.exchange)"""
        return self._grid_exchange

    @property
    def household(self) -> float:
        """Calculated power required by household."""
        return self._household
