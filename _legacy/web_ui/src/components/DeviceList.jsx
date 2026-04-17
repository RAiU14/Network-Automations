import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './DeviceList.css';

const DeviceList = ({ onSelectDevice }) => {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [pinging, setPinging] = useState({});
    const API_URL = '/api';

    useEffect(() => {
        fetchDevices();
    }, []);

    const fetchDevices = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_URL}/devices`);
            setDevices(res.data);
        } catch (err) {
            console.error(err);
        }
        setLoading(false);
    };

    const handlePing = async (e, deviceId) => {
        e.stopPropagation();
        setPinging(prev => ({ ...prev, [deviceId]: true }));
        try {
            const res = await axios.get(`${API_URL}/devices/${deviceId}/ping`);
            alert(`Ping result for ${res.data.ip}: ${res.data.reachable ? 'SUCCESS' : 'FAILED'}\nLatency: ${res.data.latency_ms}ms`);
        } catch (err) {
            console.error(err);
            alert('Ping failed.');
        }
        setPinging(prev => ({ ...prev, [deviceId]: false }));
    };

    return (
        <div className="inventory-container animate-fade">
            <header className="inventory-header">
                <h1>Device Inventory</h1>
                <p className="subtitle">Manage and monitor network nodes</p>
            </header>

            {loading ? (
                <div className="loader">Analyzing network landscape...</div>
            ) : (
                <div className="device-grid">
                    {devices.map(device => (
                        <div key={device.id} className="device-card glass" onClick={() => onSelectDevice(device.id)}>
                            <div className="card-top">
                                <div className="device-icon">🖧</div>
                                <div className="status-container">
                                    <span className={`status-badge ${device.is_active ? 'active' : 'inactive'}`}>
                                        {device.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                    <button 
                                        className={`ping-mini-btn ${pinging[device.id] ? 'loading' : ''}`}
                                        onClick={(e) => handlePing(e, device.id)}
                                        disabled={pinging[device.id]}
                                    >
                                        {pinging[device.id] ? '...' : '⚡ Ping'}
                                    </button>
                                </div>
                            </div>
                            <div className="card-body">
                                <h2>{device.name}</h2>
                                <p className="device-ip">{device.ip}</p>
                                <p className="device-mac" style={{fontSize: '0.8rem', opacity: 0.8, fontFamily: 'monospace'}}>{device.mac_address || 'Pending...'}</p>
                            </div>
                            <div className="card-footer">
                                <button className="details-btn">Performance Analytics →</button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default DeviceList;