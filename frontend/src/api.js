import axios from 'axios';

const API_BASE = 'http://localhost:8001';

export const getBoards = () =>
    axios.get(`${API_BASE}/boards`).then(res => res.data);

export const getColumns = (boardId) =>
    axios.get(`${API_BASE}/boards/${boardId}/columns`).then(res => res.data);

export const getPreviewCount = (boardId, columnId, filter) =>
    axios.post(`${API_BASE}/preview-count`, {
        board_id: Number(boardId),
        column_id: columnId,
        new_value: "",
        filter
    }).then(res => res.data.count);

export const startBulkUpdate = (boardId, columnId, newValue, filter) =>
    axios.post(`${API_BASE}/jobs`, {
        board_id: Number(boardId),
        column_id: columnId,
        new_value: newValue,
        filter
    }).then(res => res.data);

export const getJobStatus = (jobId) =>
    axios.get(`${API_BASE}/jobs/${jobId}`).then(res => res.data);

export const cancelJob = (jobId) =>
    axios.post(`${API_BASE}/jobs/${jobId}/cancel`).then(res => res.data);