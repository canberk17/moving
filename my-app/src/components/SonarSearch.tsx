"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

interface SearchResult {
  summary: string;
  sources: { url?: string }[];
}

export default function SonarSearch() {
  // State for the company name, search result, loading and error.
  const [company, setCompany] = useState<string>("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Function to fetch the summary from the API.
  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      // Trim the company name here so that extra spaces are removed only before sending the request.
      const response = await fetch("http://127.0.0.1:5002/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ company: company.trim() }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch data");
      }

      const data: SearchResult = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Helper function to format the review score.
  const formatReviewScore = (summary: string) => {
    const match = summary.match(/- Review score \(out of 5\):\s([\d\.]+)/i);
    if (match && match[1]) {
      return match[1].trim() + "/5";
    }
    return "N/A";
  };

  // Extract various fields from the result summary using regular expressions.
  const businessName =
    result?.summary.match(/- Business name:\s(.+?)(?=\n|$)/i)?.[1]?.trim() || "N/A";
  const accredited =
    result?.summary.match(/- Is the business accredited\?:\s(Yes|No)/i)?.[1]?.trim() || "N/A";
  const accreditationRating =
    result?.summary.match(/- BBB Accreditation rating \(F to A\+\):\s([A-F]\+?)/i)?.[1]?.trim() || "N/A";
  const address =
    result?.summary.match(/- Address:\s(.+?)(?=\n|$)/i)?.[1]?.trim() || "N/A";
  const reviewScore = result ? formatReviewScore(result.summary) : "N/A";
  
  // Get the hyperlink from the first source, if available.
  const bbbLink = result?.sources?.[0]?.url || "#";

  return (
    <div className="flex flex-col items-center p-6 space-y-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">BBB Company Info</h1>
      <div className="flex w-full space-x-2">
        <input
          value={company}
          // Removed .trim() here so users can type spaces freely.
          onChange={(e) => setCompany(e.target.value)}
          placeholder="Enter moving company name..."
          className="border p-2 rounded-md w-full"
        />
        <button
          onClick={fetchSummary}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
        >
          {loading ? <Loader2 className="animate-spin" /> : "Search"}
        </button>
      </div>
      {error && <p className="text-red-500">{error}</p>}
      {result && (
        <div className="border p-4 rounded-md shadow-md w-full bg-white">
          <p>
            <strong>Business Name:</strong>{" "}
            <a
              href={bbbLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              {businessName}
            </a>
          </p>
          <p><strong>Accredited:</strong> {accredited}</p>
          <p><strong>Accreditation Rating:</strong> {accreditationRating}</p>
          <p><strong>Address:</strong> {address}</p>
          <p><strong>Review Score:</strong> {reviewScore}</p>
        </div>
      )}
    </div>
  );
}
