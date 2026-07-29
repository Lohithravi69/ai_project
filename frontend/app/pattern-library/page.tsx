"use client";

import { useState, useEffect } from "react";
import { v6ListPatterns, v6SearchPatterns } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";

export default function PatternLibraryPage() {
  const [patterns, setPatterns] = useState<Record<string, any>[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadPatterns(cat?: string) {
    setLoading(true);
    try {
      const data = cat ? await v6ListPatterns(cat) : await v6ListPatterns();
      setPatterns(Array.isArray(data) ? data : []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPatterns(); }, []);

  async function handleSearch() {
    if (!search.trim()) {
      await loadPatterns(category);
      return;
    }
    setLoading(true);
    try {
      const data = await v6SearchPatterns(search.trim());
      setPatterns(Array.isArray(data) ? data : []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Pattern Library</h1>
      <p className="text-muted-foreground">Browse and search engineering patterns.</p>

      <Card>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <Input value={search} onChange={(e) => setSearch(e.currentTarget.value)} placeholder="Search patterns..." onKeyDown={(e) => e.key === "Enter" && handleSearch()} />
            <Button onClick={handleSearch}>Search</Button>
          </div>
          <div className="flex gap-2 flex-wrap">
            {["", "authentication", "api", "architecture", "infrastructure", "frontend", "testing"].map((cat) => (
              <Badge
                key={cat}
                className={`cursor-pointer ${category === cat ? "bg-blue-100 text-blue-800" : ""}`}
                onClick={() => { setCategory(cat); loadPatterns(cat || undefined); }}
              >
                {cat || "All"}
              </Badge>
            ))}
          </div>
        </div>
      </Card>

      {loading && <p>Loading...</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {patterns.map((p, i) => (
          <Card key={i}>
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="font-medium">{p.name}</h2>
                <Badge>{p.category}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{p.description}</p>
              {p.dependencies?.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  Dependencies: {p.dependencies.join(", ")}
                </div>
              )}
              {p.best_practices?.length > 0 && (
                <div>
                  <p className="text-xs font-medium">Best Practices:</p>
                  <ul className="list-disc pl-4 text-xs text-muted-foreground">
                    {p.best_practices.slice(0, 3).map((bp: string, j: number) => (
                      <li key={j}>{bp}</li>
                    ))}
                  </ul>
                </div>
              )}
              {p.template_code && (
                <details>
                  <summary className="text-xs cursor-pointer text-blue-600">View template</summary>
                  <pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-x-auto max-h-40">{p.template_code}</pre>
                </details>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
