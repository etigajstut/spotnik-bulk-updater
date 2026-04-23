import React, { useState, useEffect } from "react";
import { Dropdown, Button, Text, Box } from "monday-ui-react-core";
import { getColumns, getPreviewCount } from "../api.js";

export default function ConfigurationPanel({ boards, onStart, activeJobId, contextBoardId }) {
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [selectedColumn, setSelectedColumn] = useState(null);
  const [selectedFilterColumn, setSelectedFilterColumn] = useState(null);
  const [selectedFilterValue, setSelectedFilterValue] = useState(null);
  const [selectedNewValue, setSelectedNewValue] = useState(null);
  const [columns, setColumns] = useState([]);
  const [previewCount, setPreviewCount] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Board options computed here so the auto-select effect below can use it
  const boardOptions = boards
    .filter(b => !b.name.toLowerCase().includes("subitems"))
    .map(b => ({ label: b.name, value: String(b.id) }));

  // Auto-select the current board when the app runs inside monday.com
  useEffect(() => {
    if (!contextBoardId || selectedBoard || boardOptions.length === 0) return;
    const match = boardOptions.find(b => b.value === contextBoardId);
    if (match) setSelectedBoard(match);
  }, [contextBoardId, boardOptions.length]);

  // Fetch columns when board is selected
  useEffect(() => {
    if (!selectedBoard) return;
    setSelectedColumn(null);
    setSelectedFilterColumn(null);
    setSelectedFilterValue(null);
    setSelectedNewValue(null);
    setColumns([]);
    getColumns(selectedBoard.value).then(setColumns);
  }, [selectedBoard]);

  // Fetch preview count when column or filter changes
  useEffect(() => {
    if (!selectedBoard || !selectedColumn) { setPreviewCount(null); return; }
    setPreviewLoading(true);
    const filter = selectedFilterColumn && selectedFilterValue
      ? { column_id: selectedFilterColumn.value, operator: "any_of", values: [selectedFilterValue.value] }
      : null;
    getPreviewCount(selectedBoard.value, selectedColumn.value, filter)
      .then(count => { setPreviewCount(count); setPreviewLoading(false); })
      .catch(() => setPreviewLoading(false));
  }, [selectedBoard, selectedColumn, selectedFilterColumn, selectedFilterValue]);

  // Target column options — all columns shown, non-status ones disabled
  const columnOptions = columns
    .filter(c => c.type !== "name" && c.type !== "subtasks")
    .map(c => ({
      label: c.type === "status" ? c.title : `${c.title} (${c.type})`,
      value: c.id,
      isDisabled: c.type !== "status"
    }));

  // Filter column options — all columns (can filter by any column type)
  const filterColumnOptions = columns
    .filter(c => c.type !== "name" && c.type !== "subtasks")
    .map(c => ({ label: `${c.title} (${c.type})`, value: c.id }));

  // Get label options from column settings
  const getLabelOptions = (col) => {
    if (!col) return [];
    const colData = columns.find(c => c.id === col.value);
    if (!colData) return [];
    try {
      const settings = JSON.parse(colData.settings_str);
      if (settings.labels) {
        return Object.entries(settings.labels)
          .filter(([_, v]) => v)
          .map(([index, label]) => ({ label, value: index }));
      }
    } catch (e) {}
    return [];
  };

  const newValueOptions = getLabelOptions(selectedColumn);
  const filterValueOptions = getLabelOptions(selectedFilterColumn);

  const handleStart = () => {
    if (!selectedBoard || !selectedColumn || !selectedNewValue) return;
    const filter = selectedFilterColumn && selectedFilterValue
      ? { column_id: selectedFilterColumn.value, operator: "any_of", values: [selectedFilterValue.value] }
      : null;
    onStart(selectedBoard.value, selectedColumn.value, selectedNewValue.label, filter);
  };

  return (
    <Box style={{ display: "flex", flexDirection: "column", gap: "20px" }}>

      {/* Section 1 */}
      <Text type="text1" weight="medium">1. Select target</Text>

      <Dropdown
        placeholder="Select a board..."
        options={boardOptions}
        value={selectedBoard}
        onChange={setSelectedBoard}
        disabled={!!activeJobId}
        insideOverflowContainer
      />

      {selectedBoard && (
        <Dropdown
          placeholder="Select a column..."
          options={columnOptions}
          value={selectedColumn}
          onChange={(opt) => { setSelectedColumn(opt); setSelectedNewValue(null); }}
          disabled={!!activeJobId}
          insideOverflowContainer
        />
      )}

      {/* Section 2 */}
      {selectedColumn && (
        <>
          <Text type="text1" weight="medium">2. Filter items (optional)</Text>

          <Dropdown
            placeholder="Filter by column... (optional)"
            options={filterColumnOptions}
            value={selectedFilterColumn}
            onChange={(opt) => { setSelectedFilterColumn(opt); setSelectedFilterValue(null); }}
            disabled={!!activeJobId}
            clearable
            insideOverflowContainer
          />

          {selectedFilterColumn && filterValueOptions.length > 0 && (
            <Dropdown
              placeholder="Select filter value..."
              options={filterValueOptions}
              value={selectedFilterValue}
              onChange={setSelectedFilterValue}
              disabled={!!activeJobId}
              clearable
              insideOverflowContainer
            />
          )}

          <Text type="text2" color="secondary">
            {previewLoading
              ? "Counting items..."
              : previewCount !== null
                ? `Found ${previewCount} items to update.`
                : ""}
          </Text>
        </>
      )}

      {/* Section 3 */}
      {selectedColumn && (
        <>
          <Text type="text1" weight="medium">3. New value</Text>
          {newValueOptions.length > 0 ? (
            <Dropdown
              placeholder="Select new value..."
              options={newValueOptions}
              value={selectedNewValue}
              onChange={setSelectedNewValue}
              disabled={!!activeJobId}
              insideOverflowContainer
            />
          ) : (
            <input
              style={{ width: "100%", padding: "8px 12px", border: "1px solid #c3c6d4", borderRadius: "4px", fontSize: "14px", height: "40px" }}
              placeholder="Enter new value..."
              onChange={(e) => setSelectedNewValue({ label: e.target.value, value: e.target.value })}
              disabled={!!activeJobId}
            />
          )}
        </>
      )}

      {/* Start button */}
      {!activeJobId && selectedBoard && selectedColumn && selectedNewValue && (
        <Button
          onClick={handleStart}
          disabled={previewCount === 0}
          size={Button.sizes.LARGE}
          style={{ width: "100%", marginTop: "10px" }}>
          Start bulk update
        </Button>
      )}

    </Box>
  );
}
