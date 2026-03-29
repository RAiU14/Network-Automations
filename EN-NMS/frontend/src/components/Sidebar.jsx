import React from 'react';
import './Sidebar.css';

const Sidebar = ({ activeTab, setActiveTab, theme, toggleTheme }) => {
  const navItems = [
    { id: 'overview', label: 'Dashboard', icon: '📊' },
    { id: 'devices', label: 'Devices', icon: '🖧' },
    { id: 'analytics', label: 'Analytics', icon: '📈' },
    { id: 'logs', label: 'Audit Logs', icon: '📜' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <aside className="sidebar glass">
      <div className="sidebar-header">
        <div className="logo-icon">EN</div>
        <span className="logo-text">NMS <small>PRO</small></span>
      </div>
      
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="theme-toggle" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
        </button>
        <div className="user-profile">
          <div className="avatar">AD</div>
          <div className="user-info">
            <span className="name">Admin User</span>
            <span className="role">Network Architect</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
