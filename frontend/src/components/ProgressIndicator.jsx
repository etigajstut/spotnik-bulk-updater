import React, { useEffect, useState } from "react";
import { LinearProgressBar, Text, Box, Button } from "monday-ui-react-core";
import { getJobStatus, cancelJob } from "../api.js";
import mondaySdk from "monday-sdk-js";

const monday = mondaySdk();

export default function ProgressIndicator({ jobId, onDone, onClear }) {
  const [status, setStatus] = useState("running");
  const [processed, setProcessed] = useState(0);
  const [failed, setFailed] = useState(0);
  const [total, setTotal] = useState(1);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    let interval;
    if (status === "running") {
      interval = setInterval(async () => {
        try {
          const data = await getJobStatus(jobId);
          if (data) {
            setProcessed(data.processed || 0);
            setFailed(data.failed || 0);
            setTotal(data.total || 1);

            const isFinished = data.status === "succeeded" || data.status === "failed" ||
                              data.status === "canceled" ||
                              (data.processed > 0 && data.processed >= data.total);

            if (isFinished) {
              const finalStatus = data.status === "failed" ? "failed" : data.status === "canceled" ? "canceled" : "completed";
              setStatus(finalStatus);
              clearInterval(interval);
              onDone && onDone(finalStatus);

              // Show a native monday.com notification when running inside the platform
              if (finalStatus === "completed") {
                monday.execute("notice", {
                  message: data.failed > 0
                    ? `Bulk update done — ${data.processed} updated, ${data.failed} failed.`
                    : `Bulk update complete — ${data.processed} items updated successfully!`,
                  type: data.failed > 0 ? "error" : "success",
                  timeout: 7000
                });
              }
            } else {
              setStatus(data.status || "running");
            }
            setMsg(data.message || "");
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 1000);
    }

    return () => clearInterval(interval);
  }, [jobId, status, onDone]);

  const percentage = Math.round((processed / total) * 100) || 0;

  return (
    <Box style={{ padding: "20px", width: "100%", display: "flex", flexDirection: "column", gap: "15px", alignItems: "center" }}>
      <Text type="text1" weight="medium">
        {status === "completed" ? "Successfully Completed" : status === "failed" ? "Update Failed" : "Updating Items..."}
      </Text>

      <div style={{ width: "100%", maxWidth: "600px" }}>
        <LinearProgressBar value={percentage} />
      </div>

      <Text type="text2" color="secondary">
        {processed} / {total} Completed ({percentage}%)
        {failed > 0 && ` · ${failed} failed`}
      </Text>

      {status === "running" && (
        <Button
          onClick={() => cancelJob(jobId)}
          kind="secondary"
          size={Button.sizes.SMALL}>
          Cancel
        </Button>
      )}

      {status === "canceled" && (
        <Box style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px", marginTop: "10px" }}>
          <Text color="secondary">Update cancelled.</Text>
          <Button onClick={onClear} kind="secondary">Clear & Start New Update</Button>
        </Box>
      )}

      {status === "completed" && (
        <Box style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px", marginTop: "10px" }}>
          {failed === 0
            ? <Text color="positive" weight="bold">All items successfully updated!</Text>
            : <Text color="warning" weight="bold">{processed} updated, {failed} could not be updated (rate limited — try again).</Text>
          }
          <Button onClick={onClear} kind="secondary">Clear & Start New Update</Button>
        </Box>
      )}
      {status === "failed" && (
        <Box style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px", marginTop: "10px" }}>
          <Text color="negative">Update failed: {msg}</Text>
          <Button onClick={onClear} kind="secondary">Clear & Start New Update</Button>
        </Box>
      )}
    </Box>
  );
}
