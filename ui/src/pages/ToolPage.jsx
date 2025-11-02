import React from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function ToolPage() {
  const { toolId } = useParams();
  const [params] = useSearchParams();
  const fileUrl = params.get("file");

  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-50 p-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Tool: {toolId}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4">
            File URL:{" "}
            <a
              href={fileUrl}
              className="text-blue-600 underline"
              target="_blank"
              rel="noreferrer"
            >
              {fileUrl}
            </a>
          </p>
          <p className="text-gray-600">
            Here you would implement the {toolId} functionality.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
