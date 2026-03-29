import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './DeviceList.css';

const DeviceList = ({ onSelectDevice }) => {
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const API_URL = 'http://localhost:8000/api';

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
                                <span className={`status-badge ${device.is_active ? 'active' : 'inactive'}`}>
                                    {device.is_active ? 'Online' : 'Offline'}
                                </span>
                            </div>
                            <div className="card-body">
                                <h2>{device.name}</h2>
                                <p className="device-ip">{device.ip}</p>
                                <p className="device-mac" style={{fontSize: '0.8rem', opacity: 0.8, fontFamily: 'monospace'}}>{device.mac_address || '00:00:00:00:00:00'}</p>
                                <div className="device-meta">
                                     <div className="meta-item">
                                          <span className="label">Uptime</span>
                                          <span className="value">99.9%</span>
                                     </div>
                                     <div className="meta-item">
                                          <span className="label">Latency</span>
                                          <span className="value">12ms</span>
                                     </div>
                                </div>
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