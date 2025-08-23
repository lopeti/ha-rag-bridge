#!/usr/bin/env python3
"""Home Assistant Configuration Advisor

Analyzes Home Assistant configuration to identify non-optimally configured
entities and devices, providing actionable recommendations for improvement.

The advisor performs the following analyses:
- Entity optimization: orphaned entities, naming issues, missing areas
- Device optimization: area assignments, naming consistency
- Best practices: friendly names, device classes, entity categories
"""

from __future__ import annotations

import os
import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import re

import httpx
from arango import ArangoClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ha_rag_bridge.logging import get_logger
from ha_rag_bridge.settings import HTTP_TIMEOUT
from app.services.integrations.embeddings.friendly_name_generator import (
    FriendlyNameGenerator,
)

logger = get_logger(__name__)
console = Console()


class IssueLevel(Enum):
    """Issue severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueCategory(Enum):
    """Issue categories"""

    ENTITY_ORPHANED = "entity_orphaned"
    ENTITY_NAMING = "entity_naming"
    DEVICE_AREA = "device_area"
    DEVICE_NAMING = "device_naming"
    FRIENDLY_NAME = "friendly_name"
    DEVICE_CLASS = "device_class"
    ENTITY_CATEGORY = "entity_category"
    AREA_CONSISTENCY = "area_consistency"
    REDUNDANT_AREA = "redundant_area"


@dataclass
class ConfigIssue:
    """Represents a configuration issue with actionable recommendations"""

    entity_id: Optional[str] = None
    device_id: Optional[str] = None
    area_id: Optional[str] = None
    category: IssueCategory = IssueCategory.ENTITY_ORPHANED
    level: IssueLevel = IssueLevel.INFO
    title: str = ""
    description: str = ""
    recommendation: str = ""
    auto_fixable: bool = False
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class AnalysisReport:
    """Complete analysis report with categorized issues"""

    total_entities: int = 0
    total_devices: int = 0
    total_areas: int = 0
    issues: List[ConfigIssue] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)


class HAConfigAdvisor:
    """Main advisor class that analyzes HA configuration"""

    def __init__(self):
        """Initialize the advisor with database and API connections"""
        self.console = Console()

        # Initialize ArangoDB connection
        self.arango = ArangoClient(hosts=os.environ["ARANGO_URL"])
        db_name = os.getenv("ARANGO_DB", "_system")
        self.db = self.arango.db(
            db_name,
            username=os.environ["ARANGO_USER"],
            password=os.environ["ARANGO_PASS"],
        )

        # Initialize HA API connection
        self.ha_url = os.environ["HA_URL"]
        self.ha_token = os.environ["HA_TOKEN"]
        self.headers = {"Authorization": f"Bearer {self.ha_token}"}

        # Initialize friendly name generator
        self.friendly_name_generator = FriendlyNameGenerator()

        # Analysis data
        self.entities: List[Dict] = []
        self.devices: List[Dict] = []
        self.areas: List[Dict] = []
        self.area_map: Dict[str, str] = {}

    def fetch_ha_data(self) -> None:
        """Fetch current HA data from the RAG API"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Fetching Home Assistant data...", total=None)

            with httpx.Client(
                base_url=self.ha_url, headers=self.headers, timeout=HTTP_TIMEOUT
            ) as client:
                try:
                    resp = client.get("/api/rag/static/entities")
                    resp.raise_for_status()
                    data = resp.json()

                    self.entities = data.get("entities", [])
                    self.devices = data.get("devices", [])
                    self.areas = data.get("areas", [])

                    # Build area mapping
                    self.area_map = {}
                    for area in self.areas:
                        area_id = area.get("area_id") or area.get("id")
                        if area_id and area.get("name"):
                            self.area_map[area_id] = area["name"]

                    progress.update(task, completed=True)

                except Exception as e:
                    logger.error(f"Failed to fetch HA data: {e}")
                    raise

    def analyze_entities(self) -> List[ConfigIssue]:
        """Analyze entities for configuration issues"""
        issues = []

        # Build device area mapping
        device_area_map = {}
        for device in self.devices:
            device_id = device.get("id") or device.get("device_id", "")
            if device_id and device.get("area_id"):
                device_area_map[device_id] = device["area_id"]

        for entity in self.entities:
            entity_id = entity.get("entity_id", "")
            if not entity_id:
                continue

            entity_area_id = entity.get("area_id")
            device_id = entity.get("device_id")
            device_area_id = device_area_map.get(device_id) if device_id else None

            # Check for truly orphaned entities (neither entity nor device has area)
            if not entity_area_id and not device_area_id:
                issues.append(
                    ConfigIssue(
                        entity_id=entity_id,
                        category=IssueCategory.ENTITY_ORPHANED,
                        level=IssueLevel.WARNING,
                        title="Entity and its device have no area assignment",
                        description=f"Entity {entity_id} and its device both lack area assignment",
                        recommendation="Assign area to the device (preferred) or directly to the entity",
                        auto_fixable=False,
                        metadata={
                            "friendly_name": entity.get("friendly_name", ""),
                            "device_id": device_id,
                        },
                    )
                )

            # Check for redundant area assignment (entity area same as device area)
            elif entity_area_id and device_area_id and entity_area_id == device_area_id:
                issues.append(
                    ConfigIssue(
                        entity_id=entity_id,
                        category=IssueCategory.REDUNDANT_AREA,
                        level=IssueLevel.WARNING,
                        title="Redundant entity area assignment",
                        description=f"Entity {entity_id} has same area as its device - inheritance is sufficient",
                        recommendation="Remove entity area assignment to let it inherit from device",
                        auto_fixable=True,
                        current_value=entity_area_id,
                        suggested_value=None,
                        metadata={
                            "device_area": device_area_id,
                            "device_id": device_id,
                        },
                    )
                )

            # Check friendly name quality
            friendly_name = entity.get("friendly_name", "")

            if not friendly_name:
                issues.append(
                    ConfigIssue(
                        entity_id=entity_id,
                        category=IssueCategory.FRIENDLY_NAME,
                        level=IssueLevel.INFO,
                        title="Missing friendly name",
                        description=f"Entity {entity_id} has no friendly name set",
                        recommendation="Set a descriptive friendly name for better user experience",
                        auto_fixable=False,
                    )
                )
            elif self._is_poor_friendly_name(friendly_name, entity_id):
                suggestion = self._suggest_friendly_name(entity_id, friendly_name)
                issues.append(
                    ConfigIssue(
                        entity_id=entity_id,
                        category=IssueCategory.FRIENDLY_NAME,
                        level=IssueLevel.INFO,
                        title="Generic or unclear friendly name",
                        description=f"Friendly name '{friendly_name}' could be more descriptive",
                        recommendation=f"Consider renaming to something like '{suggestion}'",
                        auto_fixable=False,
                        current_value=friendly_name,
                        suggested_value=suggestion,
                    )
                )

            # Check device class assignment
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            device_class = entity.get("device_class")

            if domain == "sensor" and not device_class:
                # Suggest device class based on entity name/unit
                suggested_class = self._suggest_device_class(entity)
                if suggested_class:
                    issues.append(
                        ConfigIssue(
                            entity_id=entity_id,
                            category=IssueCategory.DEVICE_CLASS,
                            level=IssueLevel.INFO,
                            title="Missing device class",
                            description=f"Sensor {entity_id} would benefit from a device class",
                            recommendation=f"Consider setting device_class to '{suggested_class}'",
                            auto_fixable=False,
                            suggested_value=suggested_class,
                            metadata={"unit": entity.get("unit_of_measurement", "")},
                        )
                    )

        return issues

    def analyze_devices(self) -> List[ConfigIssue]:
        """Analyze devices for configuration issues"""
        issues = []

        for device in self.devices:
            device_id = device.get("id") or device.get("device_id", "")
            if not device_id:
                continue

            # Check for devices without area assignment
            area_id = device.get("area_id")
            if not area_id:
                issues.append(
                    ConfigIssue(
                        device_id=device_id,
                        category=IssueCategory.DEVICE_AREA,
                        level=IssueLevel.WARNING,
                        title="Device has no area assignment",
                        description=f"Device '{device.get('name', device_id)}' is not assigned to any area",
                        recommendation="Assign this device to an appropriate area in Home Assistant",
                        auto_fixable=False,
                        metadata={"name": device.get("name", "")},
                    )
                )

            # Check device naming
            device_name = device.get("name", "")
            if not device_name:
                issues.append(
                    ConfigIssue(
                        device_id=device_id,
                        category=IssueCategory.DEVICE_NAMING,
                        level=IssueLevel.INFO,
                        title="Device has no name",
                        description=f"Device {device_id} has no descriptive name",
                        recommendation="Set a descriptive name for this device",
                        auto_fixable=False,
                    )
                )
            elif self._is_poor_device_name(device_name):
                suggestion = self._suggest_device_name(device)
                issues.append(
                    ConfigIssue(
                        device_id=device_id,
                        category=IssueCategory.DEVICE_NAMING,
                        level=IssueLevel.INFO,
                        title="Generic device name",
                        description=f"Device name '{device_name}' could be more descriptive",
                        recommendation=f"Consider renaming to something like '{suggestion}'",
                        auto_fixable=False,
                        current_value=device_name,
                        suggested_value=suggestion,
                    )
                )

        return issues

    def analyze_area_consistency(self) -> List[ConfigIssue]:
        """Analyze area assignment consistency"""
        issues = []

        # Find entities that could be grouped better
        area_entity_map: Dict[str, List[Any]] = {}
        for entity in self.entities:
            area_id = entity.get("area_id")
            if area_id:
                if area_id not in area_entity_map:
                    area_entity_map[area_id] = []
                area_entity_map[area_id].append(entity)

        # Look for similar entities in different areas
        similar_entities = self._find_similar_entities_across_areas()
        for group in similar_entities:
            if len(group) > 1:
                areas = [e.get("area_id") for e in group if e.get("area_id")]
                if len(set(areas)) > 1:
                    entity_names = [e.get("entity_id", "") for e in group]
                    issues.append(
                        ConfigIssue(
                            category=IssueCategory.AREA_CONSISTENCY,
                            level=IssueLevel.INFO,
                            title="Similar entities in different areas",
                            description=f"Similar entities found across areas: {', '.join(entity_names)}",
                            recommendation="Review if these entities should be grouped in the same area",
                            auto_fixable=False,
                            metadata={
                                "entities": entity_names,
                                "areas": list(set(areas)),
                            },
                        )
                    )

        return issues

    def generate_report(self) -> AnalysisReport:
        """Generate complete analysis report"""
        all_issues = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:

            task1 = progress.add_task("Analyzing entities...", total=None)
            entity_issues = self.analyze_entities()
            all_issues.extend(entity_issues)
            progress.update(task1, completed=True)

            task2 = progress.add_task("Analyzing devices...", total=None)
            device_issues = self.analyze_devices()
            all_issues.extend(device_issues)
            progress.update(task2, completed=True)

            task3 = progress.add_task("Analyzing area consistency...", total=None)
            area_issues = self.analyze_area_consistency()
            all_issues.extend(area_issues)
            progress.update(task3, completed=True)

        # Generate summary statistics
        summary: Dict[str, Any] = {}
        for issue in all_issues:
            level_key = f"{issue.level.value}_count"
            category_key = f"{issue.category.value}_count"
            summary[level_key] = summary.get(level_key, 0) + 1
            summary[category_key] = summary.get(category_key, 0) + 1

        # Generate high-level recommendations
        recommendations = self._generate_recommendations(all_issues)

        return AnalysisReport(
            total_entities=len(self.entities),
            total_devices=len(self.devices),
            total_areas=len(self.areas),
            issues=all_issues,
            summary=summary,
            recommendations=recommendations,
        )

    def _is_poor_friendly_name(self, friendly_name: str, entity_id: str) -> bool:
        """Check if friendly name is generic or unclear"""
        # Generic patterns that indicate poor naming
        generic_patterns = [
            r"^[A-Z0-9_-]+$",  # ALL_CAPS_WITH_UNDERSCORES
            r"^(sensor|switch|light|climate)\d*$",  # Just domain + number
            r"^device\d*$",  # Generic "device" names
            r"^unnamed",  # Unnamed devices
        ]

        for pattern in generic_patterns:
            if re.match(pattern, friendly_name, re.IGNORECASE):
                return True

        # Check if friendly name is too similar to entity_id
        name_clean = friendly_name.lower().replace(" ", "_").replace("-", "_")
        entity_name = entity_id.split(".")[-1] if "." in entity_id else entity_id

        return name_clean == entity_name.lower()

    def _suggest_friendly_name(self, entity_id: str, current_name: str) -> str:
        """Suggest a better friendly name"""
        entity_name = entity_id.split(".")[-1] if "." in entity_id else entity_id

        # Basic suggestions based on domain and entity structure
        suggestions = {
            "temperature": "Temperature Sensor",
            "humidity": "Humidity Sensor",
            "power": "Power Monitor",
            "energy": "Energy Meter",
            "light": "Light",
            "switch": "Switch",
        }

        for keyword, suggestion in suggestions.items():
            if keyword in entity_name.lower():
                return suggestion

        # Fallback: capitalize and clean up entity name
        clean_name = entity_name.replace("_", " ").title()
        return clean_name

    def _suggest_device_class(self, entity: dict) -> Optional[str]:
        """Suggest appropriate device class for sensor"""
        entity_id = entity.get("entity_id", "") or ""
        unit = entity.get("unit_of_measurement", "") or ""
        friendly_name = entity.get("friendly_name", "") or ""

        entity_id = entity_id.lower()
        unit = unit.lower()
        friendly_name = friendly_name.lower()

        # Map common patterns to device classes
        class_mapping = {
            "temperature": ["°c", "celsius", "temp", "hőmérséklet"],
            "humidity": ["%", "humidity", "páratartalom", "nedvesség"],
            "power": ["w", "watt", "power", "fogyasztás"],
            "energy": ["kwh", "energy", "energia"],
            "illuminance": ["lx", "lux", "light", "fény"],
            "pressure": ["hpa", "mbar", "pressure", "nyomás"],
            "battery": ["battery", "akkumulátor"],
        }

        text_to_check = f"{entity_id} {unit} {friendly_name}"

        for device_class, keywords in class_mapping.items():
            if any(keyword in text_to_check for keyword in keywords):
                return device_class

        return None

    def _is_poor_device_name(self, device_name: str) -> bool:
        """Check if device name is generic"""
        generic_patterns = [
            r"^[A-F0-9]{12}$",  # MAC addresses
            r"^device\d*$",  # Generic "device" names
            r"^[A-Z0-9_-]+$",  # ALL_CAPS_WITH_UNDERSCORES
            r"^unnamed",  # Unnamed devices
            r"^\d+\.\d+\.\d+\.\d+$",  # IP addresses
        ]

        for pattern in generic_patterns:
            if re.match(pattern, device_name, re.IGNORECASE):
                return True

        return False

    def _suggest_device_name(self, device: dict) -> str:
        """Suggest better device name"""
        manufacturer = device.get("manufacturer", "")
        model = device.get("model", "")
        area_id = device.get("area_id", "")
        area_name = self.area_map.get(area_id, "")

        suggestions = []
        if area_name:
            suggestions.append(area_name)
        if manufacturer and model:
            suggestions.append(f"{manufacturer} {model}")
        elif manufacturer:
            suggestions.append(manufacturer)
        elif model:
            suggestions.append(model)

        return " ".join(suggestions) if suggestions else "Smart Device"

    def _find_similar_entities_across_areas(self) -> List[List[dict]]:
        """Find groups of similar entities that might belong together"""
        # Group entities by domain and device class
        groups: Dict[str, List[Any]] = {}

        for entity in self.entities:
            domain = (
                entity.get("entity_id", "").split(".")[0]
                if entity.get("entity_id")
                else ""
            )
            device_class = entity.get("device_class", "")
            unit = entity.get("unit_of_measurement", "")

            key = f"{domain}_{device_class}_{unit}"
            if key not in groups:
                groups[key] = []
            groups[key].append(entity)

        # Return groups with multiple entities
        return [group for group in groups.values() if len(group) > 1]

    def _generate_recommendations(self, issues: List[ConfigIssue]) -> List[str]:
        """Generate high-level recommendations based on issues found"""
        recommendations = []

        orphaned_entities = len(
            [i for i in issues if i.category == IssueCategory.ENTITY_ORPHANED]
        )
        orphaned_devices = len(
            [i for i in issues if i.category == IssueCategory.DEVICE_AREA]
        )
        naming_issues = len(
            [
                i
                for i in issues
                if i.category
                in [IssueCategory.FRIENDLY_NAME, IssueCategory.DEVICE_NAMING]
            ]
        )

        if orphaned_entities > 0:
            recommendations.append(
                f"Assign areas to {orphaned_entities} orphaned entities for better organization"
            )

        if orphaned_devices > 0:
            recommendations.append(
                f"Assign areas to {orphaned_devices} devices to improve entity grouping"
            )

        if naming_issues > 5:
            recommendations.append(
                "Consider reviewing entity and device names for better clarity"
            )

        if len(self.areas) < 5 and len(self.entities) > 20:
            recommendations.append(
                "Consider creating more areas to better organize your entities"
            )

        recommendations.append(
            "Run the advisor regularly to maintain optimal configuration"
        )

        return recommendations

    def display_report(self, report: AnalysisReport, show_details: bool = True) -> None:
        """Display analysis report in a formatted way"""
        # Title
        title = Panel.fit(
            "[bold blue]🏠 Home Assistant Configuration Advisor Report[/bold blue]",
            border_style="blue",
        )
        console.print(title)
        console.print()

        # Summary statistics
        summary_table = Table(title="📊 Configuration Summary", show_header=True)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", justify="right", style="white")

        summary_table.add_row("Total Entities", str(report.total_entities))
        summary_table.add_row("Total Devices", str(report.total_devices))
        summary_table.add_row("Total Areas", str(report.total_areas))
        summary_table.add_row("Total Issues", str(len(report.issues)))

        # Issue counts by level
        for level in IssueLevel:
            count = report.summary.get(f"{level.value}_count", 0)
            if count > 0:
                color = {
                    "critical": "red",
                    "error": "red",
                    "warning": "yellow",
                    "info": "blue",
                }.get(level.value, "white")
                summary_table.add_row(
                    f"{level.value.title()} Issues", str(count), style=color
                )

        console.print(summary_table)
        console.print()

        # High-level recommendations
        if report.recommendations:
            console.print("[bold green]💡 Key Recommendations[/bold green]")
            for i, rec in enumerate(report.recommendations, 1):
                console.print(f"{i}. {rec}")
            console.print()

        # Detailed issues if requested
        if show_details and report.issues:
            console.print("[bold yellow]🔍 Detailed Issues[/bold yellow]")

            # Group issues by category
            issues_by_category: Dict[str, List[Any]] = {}
            for issue in report.issues:
                category = issue.category.value
                if category not in issues_by_category:
                    issues_by_category[category] = []
                issues_by_category[category].append(issue)

            for category, issues in issues_by_category.items():
                console.print(
                    f"\n[bold]{category.replace('_', ' ').title()}[/bold] ({len(issues)} issues)"
                )

                for issue in issues[:5]:  # Show first 5 issues per category
                    level_color = {
                        "critical": "red",
                        "error": "red",
                        "warning": "yellow",
                        "info": "blue",
                    }[issue.level.value]
                    console.print(f"  [{level_color}]●[/{level_color}] {issue.title}")
                    if issue.entity_id:
                        console.print(f"    Entity: {issue.entity_id}")
                    if issue.device_id:
                        console.print(f"    Device: {issue.device_id}")
                    console.print(f"    {issue.description}")
                    console.print(f"    💡 {issue.recommendation}")
                    console.print()

                if len(issues) > 5:
                    console.print(
                        f"  ... and {len(issues) - 5} more issues in this category"
                    )

        console.print(
            f"[dim]Report generated at: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )

    def generate_friendly_name_suggestions(
        self, min_confidence: float = 0.7
    ) -> List[Dict]:
        """Generate friendly name suggestions for entities that don't have them"""
        suggestions = []

        for entity in self.entities:
            if not entity.get("friendly_name"):
                suggestion = self.friendly_name_generator.generate_suggestion(entity)
                if suggestion.confidence >= min_confidence:
                    suggestions.append(
                        {
                            "entity_id": suggestion.entity_id,
                            "suggested_name": suggestion.suggested_name,
                            "confidence": suggestion.confidence,
                            "reasoning": suggestion.reasoning,
                            "domain": suggestion.domain,
                            "area": suggestion.area_context,
                        }
                    )

        return suggestions

    def apply_friendly_name_suggestions(
        self, suggestions: List[Dict], dry_run: bool = True
    ) -> Dict:
        """Apply friendly name suggestions using the HA RAG API"""

        if dry_run:
            return {
                "dry_run": True,
                "would_update": len(suggestions),
                "suggestions": suggestions,
            }

        # Prepare batch update
        updates = [
            {"entity_id": s["entity_id"], "friendly_name": s["suggested_name"]}
            for s in suggestions
        ]

        try:
            with httpx.Client(
                base_url=self.ha_url, headers=self.headers, timeout=HTTP_TIMEOUT
            ) as client:
                response = client.post(
                    "/api/rag/batch_update_friendly_names", json={"updates": updates}
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "success": result.get("success", False),
                    "updated": result.get("updated", 0),
                    "results": result.get("results", []),
                    "errors": result.get("errors", []),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Home Assistant Configuration Advisor")
    parser.add_argument(
        "--format",
        choices=["console", "json"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--detailed", action="store_true", help="Show detailed issue breakdown"
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in IssueCategory],
        help="Filter issues by category",
    )
    parser.add_argument(
        "--level",
        choices=[level.value for level in IssueLevel],
        help="Filter issues by severity level",
    )
    parser.add_argument(
        "--suggest-friendly-names",
        action="store_true",
        help="Generate friendly name suggestions",
    )
    parser.add_argument(
        "--apply-friendly-names",
        action="store_true",
        help="Apply friendly name suggestions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without applying changes",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for suggestions (default: 0.7)",
    )

    args = parser.parse_args()

    try:
        advisor = HAConfigAdvisor()
        advisor.fetch_ha_data()

        # Handle friendly name operations
        if args.suggest_friendly_names or args.apply_friendly_names:
            suggestions = advisor.generate_friendly_name_suggestions(
                min_confidence=args.confidence
            )

            if args.suggest_friendly_names:
                console.print("[bold green]🧠 Friendly Name Suggestions[/bold green]")

                if not suggestions:
                    console.print(
                        "No suggestions found with the specified confidence threshold."
                    )
                    return 0

                table = Table(
                    title=f"Friendly Name Suggestions (confidence >= {args.confidence})"
                )
                table.add_column("Entity ID", style="cyan")
                table.add_column("Suggested Name", style="green")
                table.add_column("Confidence", justify="center")
                table.add_column("Domain", style="dim")
                table.add_column("Area", style="dim")

                for s in suggestions:
                    table.add_row(
                        s["entity_id"],
                        s["suggested_name"],
                        f"{s['confidence']:.2f}",
                        s.get("domain", ""),
                        s.get("area", ""),
                    )

                console.print(table)
                console.print(f"\nFound {len(suggestions)} suggestions.")

                if not args.apply_friendly_names:
                    console.print(
                        "\nUse --apply-friendly-names to apply these suggestions."
                    )
                    return 0

            if args.apply_friendly_names:
                console.print(
                    "[bold yellow]🔄 Applying Friendly Name Suggestions[/bold yellow]"
                )

                result = advisor.apply_friendly_name_suggestions(
                    suggestions, dry_run=args.dry_run
                )

                if result.get("dry_run"):
                    console.print(
                        f"[blue]DRY RUN: Would update {result['would_update']} entities[/blue]"
                    )
                    return 0

                if result.get("success"):
                    console.print(
                        f"[green]✅ Successfully updated {result['updated']} entities![/green]"
                    )
                    if result.get("errors"):
                        console.print(
                            f"[yellow]⚠️ {len(result['errors'])} errors occurred:[/yellow]"
                        )
                        for error in result["errors"]:
                            console.print(f"  • {error}")
                else:
                    console.print(
                        f"[red]❌ Update failed: {result.get('error', 'Unknown error')}[/red]"
                    )
                    return 1

                return 0

        # Regular advisor report
        report = advisor.generate_report()

        # Filter issues if requested
        if args.category or args.level:
            filtered_issues = []
            for issue in report.issues:
                if args.category and issue.category.value != args.category:
                    continue
                if args.level and issue.level.value != args.level:
                    continue
                filtered_issues.append(issue)
            report.issues = filtered_issues

        # Output report
        if args.format == "json":
            # Convert to JSON-serializable format
            report_dict = {
                "total_entities": report.total_entities,
                "total_devices": report.total_devices,
                "total_areas": report.total_areas,
                "issues": [
                    {
                        "entity_id": issue.entity_id,
                        "device_id": issue.device_id,
                        "area_id": issue.area_id,
                        "category": issue.category.value,
                        "level": issue.level.value,
                        "title": issue.title,
                        "description": issue.description,
                        "recommendation": issue.recommendation,
                        "auto_fixable": issue.auto_fixable,
                        "current_value": issue.current_value,
                        "suggested_value": issue.suggested_value,
                        "metadata": issue.metadata,
                    }
                    for issue in report.issues
                ],
                "summary": report.summary,
                "recommendations": report.recommendations,
                "generated_at": report.generated_at.isoformat(),
            }

            output_text = json.dumps(report_dict, indent=2, ensure_ascii=False)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_text)
            else:
                print(output_text)
        else:
            # Console output
            advisor.display_report(report, show_details=args.detailed)

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        console.print(f"[red]❌ Analysis failed: {e}[/red]")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
