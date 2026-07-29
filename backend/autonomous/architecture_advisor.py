from __future__ import annotations

import json
from typing import Any


class ArchitectureRecommendation:
    def __init__(
        self,
        title: str,
        category: str,
        description: str,
        rationale: str = "",
        affected_files: list[str] | None = None,
        tradeoffs: dict[str, Any] | None = None,
        confidence: float = 0.0,
        status: str = "proposed",
    ) -> None:
        self.title = title
        self.category = category
        self.description = description
        self.rationale = rationale
        self.affected_files = affected_files or []
        self.tradeoffs = tradeoffs or {}
        self.confidence = confidence
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "rationale": self.rationale,
            "affected_files": self.affected_files,
            "tradeoffs": self.tradeoffs,
            "confidence": self.confidence,
            "status": self.status,
        }


_ARCHITECTURE_HEURISTICS: list[dict[str, Any]] = [
    {
        "pattern": r"class \w+\(.*\):.*\n(?:.*\n)*.*def \w+\(self.*\):",
        "category": "design",
        "description": "Detect large classes with many methods that may violate Single Responsibility",
        "suggestion": "Consider splitting into smaller focused classes",
    },
    {
        "pattern": r"from \w+ import \*",
        "category": "import",
        "description": "Wildcard imports pollute namespace and hide dependencies",
        "suggestion": "Use explicit imports instead",
    },
    {
        "pattern": r"try:\s*\n\s+pass\s*\n\s*except:",
        "category": "error_handling",
        "description": "Bare except clauses swallow all exceptions",
        "suggestion": "Catch specific exception types",
    },
    {
        "pattern": r"def \w+\(.*\):\s*\n(?:\s+\n)*\s+pass",
        "category": "completeness",
        "description": "Empty function body (pass only)",
        "suggestion": "Implement or remove stub functions",
    },
    {
        "pattern": r"os\.system\(|subprocess\.call\(|eval\(|exec\(",
        "category": "security",
        "description": "Use of shell execution or dynamic code evaluation",
        "suggestion": "Use safer alternatives like subprocess.run with shell=False",
    },
    {
        "pattern": r"\.env|SECRET|PASSWORD|API_KEY|SECRET_KEY\s*=",
        "category": "security",
        "description": "Hardcoded secrets detected in source code",
        "suggestion": "Move secrets to environment variables or a secrets manager",
    },
    {
        "pattern": r"#\s*TODO|#\s*FIXME|#\s*HACK|#\s*XXX",
        "category": "maintainability",
        "description": "Incomplete work or technical debt markers",
        "suggestion": "Address TODOs before shipping",
    },
    {
        "pattern": r"def \w+\(.*,\s*\*\*kwargs\s*\)",
        "category": "design",
        "description": "Methods accepting **kwargs may have unclear interfaces",
        "suggestion": "Define explicit parameters where possible",
    },
    {
        "pattern": r"\.get\(|\.post\(|\.put\(|\.delete\(|\.patch\(",
        "category": "api",
        "description": "HTTP method calls in business logic",
        "suggestion": "Abstract HTTP calls behind a service layer",
    },
]


class ArchitectureAdvisor:
    def __init__(self, ollama_client: Any = None) -> None:
        self._ollama = ollama_client

    def analyze_code_quality(self, file_path: str, content: str) -> list[ArchitectureRecommendation]:
        recommendations: list[ArchitectureRecommendation] = []
        import re

        for heuristic in _ARCHITECTURE_HEURISTICS:
            if re.search(heuristic["pattern"], content, re.MULTILINE):
                recommendations.append(ArchitectureRecommendation(
                    title=heuristic["suggestion"],
                    category=heuristic["category"],
                    description=heuristic["description"],
                    affected_files=[file_path],
                    confidence=0.6,
                ))
        return recommendations

    def analyze_dependencies(self, imports: list[str], source_files: dict[str, str]) -> list[ArchitectureRecommendation]:
        recommendations: list[ArchitectureRecommendation] = []
        known_modules = set()
        for path in source_files:
            parts = path.replace("\\", "/").replace("/", ".").rstrip(".py")
            known_modules.add(parts)
            parent = ".".join(parts.split(".")[:-1])
            while parent:
                known_modules.add(parent)
                parent = ".".join(parent.split(".")[:-1])

        for imp in imports:
            if not imp.startswith("backend."):
                continue
            imp_base = imp.split(".")[0] if "." in imp else imp
            if imp_base not in known_modules and imp_base != "backend":
                recommendations.append(ArchitectureRecommendation(
                    title=f"Dependency on unknown module: {imp}",
                    category="dependency",
                    description=f"Module imports '{imp}' which doesn't exist in codebase",
                    confidence=0.9,
                ))

        cross_layer_imports: list[tuple[str, str, str]] = [
            ("backend.api", "backend.database", "API layer importing database layer directly"),
            ("backend.api", "backend.embeddings", "API layer importing embeddings layer directly"),
        ]
        for imp in imports:
            for (layer1, layer2, desc) in cross_layer_imports:
                if imp.startswith(layer2):
                    recommendations.append(ArchitectureRecommendation(
                        title=f"Cross-layer dependency: {desc}",
                        category="layering",
                        description=f"Detected import '{imp}' which crosses architectural layers. {desc}",
                        confidence=0.7,
                    ))

        return recommendations

    def rank_recommendations(
        self,
        recommendations: list[ArchitectureRecommendation],
    ) -> list[ArchitectureRecommendation]:
        score_map = {
            "security": 1.0,
            "layering": 0.9,
            "dependency": 0.8,
            "error_handling": 0.7,
            "maintainability": 0.5,
            "design": 0.4,
            "api": 0.3,
            "import": 0.2,
            "completeness": 0.1,
        }
        scored = sorted(
            recommendations,
            key=lambda r: (score_map.get(r.category, 0) * r.confidence),
            reverse=True,
        )
        return scored

    async def llm_recommend(
        self,
        context: str,
        code_snippets: list[str],
    ) -> list[dict[str, Any]]:
        if not self._ollama:
            return []
        try:
            import asyncio
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an architecture advisor. Review the code context and suggest "
                        "architectural improvements. Return a JSON list of objects with: "
                        "title (str), category (str), description (str), rationale (str), "
                        "affected_files (list of str), tradeoffs (object), confidence (float 0-1)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context: {context}\n\nCode:\n" + "\n---\n".join(code_snippets[:5]),
                },
            ]
            content = await asyncio.wait_for(self._ollama.chat(messages), timeout=12.0)
            data = json.loads(content)
            return data if isinstance(data, list) else data.get("recommendations", [])
        except Exception:
            return []
