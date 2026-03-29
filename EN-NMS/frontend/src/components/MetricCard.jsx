import React from 'react';
import './MetricCard.css';

const MetricCard = ({ title, value, unit, icon, trend, color, subValue }) => {
  return (
    <div className="metric-card glass animate-fade">
      <div className="metric-header">
        <div className="metric-icon" style={{ background: color || 'var(--accent)' }}>
          {icon}
        </div>
        <div className="metric-meta">
          <span className="metric-title">{title}</span>
          {trend && (
            <span className={`metric-trend ${trend > 0 ? 'up' : 'down'}`}>
              {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
            </span>
          )}
        </div>
      </div>
      
      <div className="metric-body">
        <span className="metric-value">{value}</span>
        {unit && <span className="metric-unit">{unit}</span>}
      </div>

      {subValue && (
          <div className="metric-footer">
               <span className="metric-sub">{subValue}</span>
          </div>
      )}
    </div>
  );
};

export default MetricCard;
