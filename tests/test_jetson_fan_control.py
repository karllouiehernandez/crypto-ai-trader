from deployment.jetson_fan_control import (
    PWM_HIGH,
    PWM_MEDIUM,
    PWM_OFF,
    next_fan_state,
    pwm_for_state,
)


def test_next_fan_state_enters_medium_then_high():
    assert next_fan_state(49.9, "off") == "off"
    assert next_fan_state(50.0, "off") == "medium"
    assert next_fan_state(58.0, "medium") == "high"


def test_next_fan_state_respects_hysteresis_when_cooling():
    assert next_fan_state(55.0, "high") == "high"
    assert next_fan_state(52.0, "high") == "medium"
    assert next_fan_state(45.0, "medium") == "medium"
    assert next_fan_state(42.0, "medium") == "off"


def test_pwm_for_state_maps_expected_values():
    assert pwm_for_state("off") == PWM_OFF
    assert pwm_for_state("medium") == PWM_MEDIUM
    assert pwm_for_state("high") == PWM_HIGH
