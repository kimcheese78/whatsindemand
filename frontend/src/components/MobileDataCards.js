import React, { useState } from 'react';

const MobileDataCards = ({
  items,
  getKey,
  getLabel,
  renderSummary,
  renderDetails,
  onExpandedChange,
  empty,
  className = '',
}) => {
  const [expandedKey, setExpandedKey] = useState(null);

  if (!items.length) {
    return <div className={`lg:hidden ${className}`}>{empty}</div>;
  }

  return (
    <div role="list" className={`lg:hidden divide-y divide-line ${className}`}>
      {items.map((item, index) => {
        const itemKey = getKey(item, index);
        const expanded = expandedKey === itemKey;
        const detailsId = `mobile-card-${String(itemKey).replace(/[^a-zA-Z0-9_-]/g, '-')}`;

        return (
          <div role="listitem" key={itemKey}>
            <button
              type="button"
              aria-label={getLabel(item, index)}
              aria-expanded={expanded}
              aria-controls={detailsId}
              onClick={() => {
                setExpandedKey(expanded ? null : itemKey);
                onExpandedChange?.(expanded ? null : item);
              }}
              className="w-full min-h-11 px-4 py-4 text-left transition-colors hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/70"
            >
              {renderSummary(item, index, expanded)}
            </button>
            {expanded && (
              <div id={detailsId} className="border-t border-line bg-black/15 px-4 py-4">
                {renderDetails(item, index)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default MobileDataCards;
