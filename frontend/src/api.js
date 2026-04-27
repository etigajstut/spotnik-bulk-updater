import axios from 'axios';
import mondaySdk from 'monday-sdk-js';

// In development: http://localhost:8001
// In monday-code: set VITE_API_BASE to the deployed backend URL before building
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001';
const monday = mondaySdk();

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

export const startBulkUpdate = async (boardId, columnId, newValue, filter, totalHint) => {
    // Get the monday session token — used by the backend to authenticate Storage API calls
    let sessionToken = null;
    try {
        const res = await monday.get('sessionToken');
        sessionToken = res.data;
    } catch (e) {
        // Not running inside monday.com (e.g. local dev) — Storage API won't be used
    }
    return axios.post(`${API_BASE}/jobs`, {
        board_id: Number(boardId),
        column_id: columnId,
        new_value: newValue,
        filter,
        total_hint: totalHint || null,
        session_token: sessionToken
    }).then(res => res.data);
};

export const getJobStatus = (jobId) =>
    axios.get(`${API_BASE}/jobs/${jobId}`).then(res => res.data);

export const cancelJob = (jobId) =>
    axios.post(`${API_BASE}/jobs/${jobId}/cancel`).then(res => res.data);