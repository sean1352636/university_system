"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def convert_units(quantity: float, from_unit: str) -> Optional[float]:
    """Convert various units to kilograms"""
    try:
        from_unit = from_unit.lower()

        # Already in kg
        if from_unit in ['kg', 'kgs', 'kilogram', 'kilograms']:
            return quantity

        # Grams to kg
        if from_unit in ['g', 'gram', 'grams']:
            return quantity / 1000

        # Pounds to kg
        if from_unit in ['lb', 'lbs', 'pound', 'pounds']:
            return quantity * 0.453592

        # Ounces to kg
        if from_unit in ['oz', 'ounce', 'ounces']:
            return quantity * 0.0283495

        print(f"❌ Unknown unit: {from_unit}")
        print("   Supported units: kg, g, lb, oz")
        return None

    except Exception as e:
        logger.error(f"Error converting units: {e}")
        return None
