#!/usr/bin/env python3
"""Intelligent Friendly Name Generator for Home Assistant entities

Generates contextual Hungarian friendly names based on entity_id patterns,
area assignments, and domain-specific knowledge.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FriendlyNameSuggestion:
    """Represents a friendly name suggestion with confidence and reasoning"""

    entity_id: str
    current_name: Optional[str]
    suggested_name: str
    confidence: float  # 0.0 - 1.0
    reasoning: str
    area_context: Optional[str] = None
    domain: Optional[str] = None


class FriendlyNameGenerator:
    """Intelligent friendly name generator with Hungarian context awareness"""

    def __init__(self):
        """Initialize the generator with translation dictionaries and patterns"""

        # Hungarian room/area translations
        self.room_translations = {
            "etkezo": "étkező",
            "furdoszoba": "fürdőszoba",
            "eloszoba": "előszoba",
            "konyha": "konyha",
            "nappali": "nappali",
            "bubi": "Bubi szoba",
            "gyerekszoba": "gyerekszoba",
            "eloter": "előtér",
            "haloszoba": "hálószoba",
            "halo": "hálószoba",
            "mosokonyha": "mosókonyha",
            "pince": "pince",
            "padlas": "padlás",
            "terasz": "terasz",
            "erkely": "erkély",
            "garazs": "garázs",
            "kert": "kert",
            "udvar": "udvar",
        }

        # Component/device translations
        self.component_translations = {
            # Lighting
            "lampa": "lámpa",
            "light": "lámpa",
            "falikar": "falikar",
            "plafon": "mennyezeti lámpa",
            "asztali": "asztali lámpa",
            "allolampa": "állólámpa",
            # Movement/sensors
            "mozgaserzekelo": "mozgásérzékelő",
            "mozgas": "mozgás",
            "occupancy": "jelenlét",
            "motion": "mozgás",
            "detector": "érzékelő",
            # Climate/environment
            "temperature": "hőmérséklet",
            "humidity": "páratartalom",
            "pressure": "légnyomás",
            "homerseklet": "hőmérséklet",
            "paratartalom": "páratartalom",
            "legnyomas": "légnyomás",
            # Covers/blinds
            "redony": "redőny",
            "rollo": "roló",
            "ablak": "ablak",
            "ajto": "ajtó",
            "cover": "redőny",
            # Electronics
            "tv": "TV",
            "television": "TV",
            "remote": "távirányító",
            "media": "média",
            "player": "lejátszó",
            # Power/energy
            "power": "áramfogyasztás",
            "energy": "energia",
            "fogyasztas": "fogyasztás",
            "aramfogyasztas": "áramfogyasztás",
            "production": "termelés",
            "battery": "akkumulátor",
            "voltage": "feszültség",
            "current": "áram",
            # Time expressions
            "today": "mai",
            "tomorrow": "holnapi",
            "now": "jelenlegi",
            "next": "következő",
            "this": "mai",
            # Appliances
            "hutogep": "hűtőgép",
            "mosogep": "mosógép",
            "szaritogep": "szárítógép",
            "suto": "sütő",
            "mikro": "mikrohullámú sütő",
            "kavefozo": "kávéfőző",
            "vacuum": "porszívó",
            "konnektor": "konnektor",
            "konektor": "konnektor",
            # Weather/outdoor
            "weather": "időjárás",
            "weatherapi": "időjárás API",
            "pm_2_5": "PM2.5",
            "pm25": "PM2.5",
            "outdoor": "kültéri",
            "indoor": "beltéri",
            "otthon": "otthon",
            # Switches/controls
            "switch": "kapcsoló",
            "button": "gomb",
            "beep": "sípolás",
            "pump": "szivattyú",
            "enabled": "engedélyezett",
            # Directional
            "left": "bal",
            "right": "jobb",
            "bal": "bal",
            "jobb": "jobb",
            "kozep": "közép",
            "center": "közép",
        }

        # Domain-specific name patterns
        self.domain_patterns = {
            "sensor": {
                "default_suffix": "szenzor",
                "measurement_patterns": {
                    ("temperature", "°c"): "hőmérséklet",
                    ("humidity", "%"): "páratartalom szenzor",
                    ("power", "w"): "áramfogyasztás",
                    ("energy", "kwh"): "energia mérő",
                    ("illuminance", "lx"): "fényerősség szenzor",
                    ("pressure", "hpa"): "légnyomás szenzor",
                    ("battery", "%"): "akkumulátor szint",
                },
            },
            "light": {
                "default_suffix": "",  # Already handled in component translations
                "positional_patterns": {
                    "ablak": "ablak világítás",
                    "asztal": "asztali lámpa",
                    "mennyezet": "mennyezeti lámpa",
                },
            },
            "binary_sensor": {
                "default_suffix": "érzékelő",
                "device_class_patterns": {
                    "occupancy": "jelenlét érzékelő",
                    "motion": "mozgás érzékelő",
                    "door": "ajtó érzékelő",
                    "window": "ablak érzékelő",
                },
            },
            "cover": {"default_suffix": "redőny"},
            "switch": {"default_suffix": "kapcsoló"},
            "climate": {"default_suffix": "klíma"},
            "media_player": {"default_suffix": "médialejátszó"},
            "weather": {"default_suffix": "időjárás"},
        }

    def generate_suggestion(self, entity_data: Dict) -> FriendlyNameSuggestion:
        """Generate friendly name suggestion for an entity"""

        entity_id = entity_data.get("entity_id", "")
        current_name = entity_data.get("friendly_name")
        area_id = entity_data.get("area_id")
        device_class = entity_data.get("device_class")
        unit_of_measurement = entity_data.get("unit_of_measurement", "")

        if not entity_id:
            return FriendlyNameSuggestion(
                entity_id="",
                current_name=current_name,
                suggested_name="",
                confidence=0.0,
                reasoning="Hiányzó entity_id",
            )

        # Parse entity components
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        name_part = entity_id.split(".")[1] if "." in entity_id else entity_id

        # Generate name components
        suggested_name, confidence, reasoning = self._build_name(
            name_part=name_part,
            domain=domain,
            area_id=area_id,
            device_class=device_class,
            unit_of_measurement=unit_of_measurement,
        )

        return FriendlyNameSuggestion(
            entity_id=entity_id,
            current_name=current_name,
            suggested_name=suggested_name,
            confidence=confidence,
            reasoning=reasoning,
            area_context=area_id,
            domain=domain,
        )

    def _build_name(
        self,
        name_part: str,
        domain: str,
        area_id: Optional[str],
        device_class: Optional[str],
        unit_of_measurement: str,
    ) -> Tuple[str, float, str]:
        """Build friendly name from components"""

        confidence = 0.8  # Base confidence
        reasoning_parts = []
        name_components = []

        # Split name_part into words
        words = name_part.replace("_", " ").lower().split()

        # Detect and translate room/area from name
        detected_room = None
        remaining_words = []

        for word in words:
            if word in self.room_translations:
                detected_room = self.room_translations[word]
                confidence += 0.1
                reasoning_parts.append(f"szoba detektálva: {word}→{detected_room}")
            else:
                remaining_words.append(word)

        # Use area_id if available and no room detected in name
        if not detected_room and area_id:
            if area_id in self.room_translations:
                detected_room = self.room_translations[area_id]
                confidence += 0.05
                reasoning_parts.append(f"area_id alapján: {area_id}→{detected_room}")
            else:
                detected_room = area_id.title()
                confidence += 0.03
                reasoning_parts.append(f"area_id használva: {area_id}")

        # Add room to beginning if detected
        if detected_room:
            name_components.append(detected_room)

        # Translate remaining component words
        translated_components = []
        for word in remaining_words:
            # Handle special patterns like "pm_2_5"
            if (
                word == "pm"
                and len(remaining_words) >= 3
                and remaining_words[
                    remaining_words.index(word) + 1 : remaining_words.index(word) + 3
                ]
                == ["2", "5"]
            ):
                translated_components.append("PM2.5")
                confidence += 0.12
                reasoning_parts.append("speciális minta: pm_2_5→PM2.5")
                # Skip the next two words (2, 5)
                remaining_words = remaining_words[remaining_words.index(word) + 3 :]
                break
            elif word in self.component_translations:
                translated = self.component_translations[word]
                translated_components.append(translated)
                confidence += 0.08
                reasoning_parts.append(f"komponens: {word}→{translated}")
            else:
                # Keep original word but capitalize
                translated_components.append(word.title())
                confidence -= 0.02  # Slight penalty for untranslated words

        # Add translated components
        name_components.extend(translated_components)

        # Apply domain-specific patterns
        if domain in self.domain_patterns:
            domain_config = self.domain_patterns[domain]

            # Check for measurement patterns (sensors)
            if (
                "measurement_patterns" in domain_config
                and device_class
                and unit_of_measurement
            ):
                pattern_key = (device_class.lower(), unit_of_measurement.lower())
                if pattern_key in domain_config["measurement_patterns"]:
                    measurement_name = domain_config["measurement_patterns"][
                        pattern_key
                    ]
                    # Replace last component with measurement name
                    if translated_components:
                        name_components[-1] = measurement_name
                    else:
                        name_components.append(measurement_name)
                    confidence += 0.15
                    reasoning_parts.append(
                        f"mérési minta: {pattern_key}→{measurement_name}"
                    )

            # Check for device class patterns
            elif "device_class_patterns" in domain_config and device_class:
                if device_class in domain_config["device_class_patterns"]:
                    class_name = domain_config["device_class_patterns"][device_class]
                    name_components.append(class_name)
                    confidence += 0.1
                    reasoning_parts.append(f"device_class: {device_class}→{class_name}")
                elif domain_config.get("default_suffix"):
                    name_components.append(domain_config["default_suffix"])
                    confidence += 0.05
                    reasoning_parts.append(f"alapértelmezett domain suffix: {domain}")

            # Add default suffix if needed and no specific pattern matched
            elif domain_config.get("default_suffix") and not any(
                reasoning
                for reasoning in reasoning_parts
                if "minta" in reasoning or "device_class" in reasoning
            ):
                name_components.append(domain_config["default_suffix"])
                confidence += 0.05
                reasoning_parts.append(f"domain suffix: {domain}")

        # Remove duplicates while preserving order
        unique_components = []
        seen = set()
        for component in name_components:
            component_lower = component.lower()
            if component_lower not in seen:
                unique_components.append(component)
                seen.add(component_lower)

        # Construct final name
        final_name = " ".join(unique_components)

        # Clean up the name
        final_name = self._clean_name(final_name)

        # Adjust confidence based on quality
        confidence = min(1.0, max(0.3, confidence))

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else "alapértelmezett név generálás"
        )

        return final_name, confidence, reasoning

    def _clean_name(self, name: str) -> str:
        """Clean and normalize the generated name"""
        # Remove extra spaces
        name = " ".join(name.split())

        # Capitalize first letter
        if name:
            name = name[0].upper() + name[1:]

        # Fix common patterns
        name = name.replace(" Szenzor", " szenzor")
        name = name.replace(" Lámpa", " lámpa")
        name = name.replace(" Kapcsoló", " kapcsoló")

        return name

    def batch_generate(self, entities: List[Dict]) -> List[FriendlyNameSuggestion]:
        """Generate suggestions for multiple entities"""
        suggestions = []
        for entity in entities:
            suggestion = self.generate_suggestion(entity)
            suggestions.append(suggestion)
        return suggestions

    def filter_suggestions(
        self,
        suggestions: List[FriendlyNameSuggestion],
        min_confidence: float = 0.5,
        domains: Optional[List[str]] = None,
    ) -> List[FriendlyNameSuggestion]:
        """Filter suggestions by confidence and domains"""
        filtered = []
        for suggestion in suggestions:
            if suggestion.confidence < min_confidence:
                continue
            if domains and suggestion.domain not in domains:
                continue
            filtered.append(suggestion)
        return filtered


def main():
    """CLI entry point for testing the generator"""
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Generate friendly name suggestions")
    parser.add_argument("--test", action="store_true", help="Run test scenarios")
    parser.add_argument("--entity-id", help="Test single entity ID")
    parser.add_argument(
        "--confidence", type=float, default=0.5, help="Minimum confidence threshold"
    )

    args = parser.parse_args()

    generator = FriendlyNameGenerator()

    if args.test:
        # Test scenarios
        test_entities = [
            {"entity_id": "light.etkezo_ablak_falikar", "area_id": "etkezo"},
            {
                "entity_id": "sensor.weatherapi_otthon_pm_2_5",
                "unit_of_measurement": "μg/m³",
            },
            {
                "entity_id": "binary_sensor.konyha_mozgaserzekelo_occupancy",
                "area_id": "konyha",
                "device_class": "occupancy",
            },
            {
                "entity_id": "sensor.energy_production_today",
                "unit_of_measurement": "kWh",
                "device_class": "energy",
            },
            {"entity_id": "cover.bubi_redony", "area_id": "bubi"},
            {
                "entity_id": "sensor.nappali_homerseklet",
                "area_id": "nappali",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            },
            {"entity_id": "switch.maci_pump_enabled"},
            {"entity_id": "weather.otthon"},
            {"entity_id": "light.furdoszoba_lampa", "area_id": "furdoszoba"},
        ]

        suggestions = generator.batch_generate(test_entities)

        print("🧠 FRIENDLY NAME GENERATOR TESZT EREDMÉNYEK\n")
        for suggestion in suggestions:
            if suggestion.confidence >= args.confidence:
                print(f"Entity: {suggestion.entity_id}")
                print(f'Javaslat: "{suggestion.suggested_name}"')
                print(f"Bizalom: {suggestion.confidence:.2f}")
                print(f"Indoklás: {suggestion.reasoning}")
                print()

    elif args.entity_id:
        # Single entity test
        entity_data = {"entity_id": args.entity_id}
        suggestion = generator.generate_suggestion(entity_data)

        result = {
            "entity_id": suggestion.entity_id,
            "suggested_name": suggestion.suggested_name,
            "confidence": suggestion.confidence,
            "reasoning": suggestion.reasoning,
        }

        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print("Use --test for test scenarios or --entity-id <id> for single entity")


if __name__ == "__main__":
    main()
