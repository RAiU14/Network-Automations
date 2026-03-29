import React, { useState } from 'react';
import './Settings.css';

const Settings = () => {
    const [intervals, setIntervals] = useState({ light: 60, heavy: 3600 });
    const [notifications, setNotifications] = useState(true);

    const handleSave = () => {
        alert('Settings saved locally. Persistence to backend coming soon.');
    };

    return (
        <div className="settings-container animate-fade">
             <header className="settings-header">
                <h1>User Settings</h1>
                <p className="subtitle">Configure your EN-NMS environment</p>
                <button className="save-btn" onClick={handleSave}>💾 Save Configuration</button>
            </header>

            <div className="settings-sections">
                <section className="settings-card glass">
                    <h3>Polling Strategy</h3>
                    <div className="input-group">
                        <label>Light Poll Interval (seconds)</label>
                        <input 
                            type="number" 
                            value={intervals.light} 
                            onChange={(e) => setIntervals({...intervals, light: e.target.value})} 
                        />
                        <p className="hint">Fast health checks (uptime, reachability).</p>
                    </div>
                    <div className="input-group">
                        <label>Heavy Poll Interval (seconds)</label>
                        <input 
                            type="number" 
                            value={intervals.heavy} 
                            onChange={(e) => setIntervals({...intervals, heavy: e.target.value})} 
                        />
                        <p className="hint">Aggregated inventory and massive data collection.</p>
                    </div>
                </section>

                <section className="settings-card glass">
                    <h3>Display & Preference</h3>
                    <div className="toggle-group">
                         <span>Real-time Alert Notifications</span>
                         <input 
                             type="checkbox" 
                             checked={notifications} 
                             onChange={() => setNotifications(!notifications)} 
                         />
                    </div>
                    <div className="input-group">
                        <label>Data Retention (Days)</label>
                        <select defaultValue="30">
                            <option value="7">7 Days</option>
                            <option value="30">30 Days</option>
                            <option value="90">90 Days</option>
                        </select>
                    </div>
                </section>

                <section className="settings-card glass danger">
                    <h3 style={{color: '#ff4d4d'}}>Advanced / Troubleshooting</h3>
                    <button className="danger-btn">Clear Polling Metrics</button>
                    <button className="danger-btn">Factory Reset System</button>
                </section>
            </div>
        </div>
    );
};

export default Settings;
