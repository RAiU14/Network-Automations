import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Overview from './components/Overview';
import DeviceList from './components/DeviceList';
import Dashboard from './components/Dashboard';
import AuditLogs from './components/AuditLogs';
import Settings from './components/Settings';
import Analytics from './components/Analytics';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
    document.body.className = savedTheme === 'light' ? 'light' : '';
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    document.body.className = newTheme === 'light' ? 'light' : '';
  };

  const onSelectDevice = (id) => {
    setSelectedDevice(id);
    setActiveTab('device-detail');
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return <Overview onSelectDevice={onSelectDevice} />;
      case 'devices':
        return <DeviceList onSelectDevice={onSelectDevice} />;
      case 'logs':
        return <AuditLogs />;
      case 'device-detail':
        return <Dashboard deviceId={selectedDevice} theme={theme} onBack={() => setActiveTab('devices')} />;
      case 'settings':
        return <Settings />;
      case 'analytics':
        return <Analytics theme={theme} />;
      default:
        return <Overview onSelectDevice={onSelectDevice} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        theme={theme} 
        toggleTheme={toggleTheme} 
      />
      <main className="main-content">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;