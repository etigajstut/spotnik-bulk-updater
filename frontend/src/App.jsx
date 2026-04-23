import React, { useState, useEffect } from "react";
import { Heading, Loader } from "monday-ui-react-core";
import "monday-ui-react-core/tokens";
import mondaySdk from "monday-sdk-js";
import { getBoards, startBulkUpdate } from "./api.js";
import ConfigurationPanel from "./components/ConfigurationPanel.jsx";
import ProgressIndicator from "./components/ProgressIndicator.jsx";

const monday = mondaySdk();

export default function App() {
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeJobId, setActiveJobId] = useState(null);
  const [error, setError] = useState(null);
  const [contextBoardId, setContextBoardId] = useState(null);

  useEffect(() => {
    // When running inside monday.com, get the current board from context
    monday.get("context").then((res) => {
      if (res.data?.boardId) {
        setContextBoardId(String(res.data.boardId));
      }
    }).catch(() => {}); // Silently ignore — not running inside monday.com

    getBoards()
      .then((data) => {
        setBoards(data || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleStartUpdate = async (boardId, columnId, newValue, filter) => {
    try {
      const response = await startBulkUpdate(boardId, columnId, newValue, filter);
      setActiveJobId(response.job_id);
    } catch (err) {
      console.error("Failed to start bulk update", err);
      alert("Failed to start update process.");
    }
  };

  const handleJobDone = () => {};

  const handleClearJob = () => {
    setActiveJobId(null);
  };

  return (
    <div style={{ padding: "30px", maxWidth: "800px", margin: "0 auto", fontFamily: "var(--font-family, Roboto)" }}>
      <Heading type="h2" weight="medium" style={{ marginBottom: "20px" }}>
        Bulk status updater
      </Heading>

      {loading ? (
        <Loader />
      ) : error ? (
        <p style={{ color: "red" }}>Error loading boards: {error}</p>
      ) : (
        <>
          <ConfigurationPanel
            boards={boards}
            onStart={handleStartUpdate}
            activeJobId={activeJobId}
            contextBoardId={contextBoardId}
          />
          {activeJobId && (
            <div style={{ marginTop: "30px", borderTop: "1px solid #e1e2e5" }}>
              <ProgressIndicator
                jobId={activeJobId}
                onDone={handleJobDone}
                onClear={handleClearJob}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
