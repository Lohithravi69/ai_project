"use client";

import { useState } from "react";
import { semanticSearch } from "../../lib/api";
import { SearchResult } from "../../lib/types";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";

export default function SemanticSearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  async function onSearch() {
    setLoading(true);
    try {
      const res = await semanticSearch(query);
      setResults(res.results);
    } catch (err) {
      console.error(err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Semantic Search</h1>
      <div className="flex gap-2 mb-4">
        <Input value={query} onChange={(e) => setQuery(e.currentTarget.value)} placeholder="Search repository..." />
        <Button onClick={onSearch} disabled={loading || !query}>{loading ? "Searching..." : "Search"}</Button>
      </div>
      <div className="grid gap-3">
        {results.map((r) => (
          <Card key={r.id}>
            <div className="p-3">
              <div className="text-sm text-muted-foreground">Score: {r.score.toFixed(3)}</div>
              <pre className="whitespace-pre-wrap text-sm mt-2">{r.content}</pre>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
