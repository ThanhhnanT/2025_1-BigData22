# Component Structure Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      TradingDashboard.tsx                       │
│                    (Main Orchestrator)                          │
│                                                                 │
│  State Management:                                              │
│  • symbol, symbols, currentTime                                 │
│  • mode, indicators, indicatorsModalOpen                        │
│                                                                 │
│  Effects:                                                       │
│  • fetchSymbols from API                                        │
│  • updateCurrentTime every second                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ├──────────────────────────┐
                              │                          │
                              ▼                          ▼
              ┌───────────────────────────┐  ┌──────────────────────────┐
              │   DashboardHeader.tsx     │  │   ControlPanel.tsx       │
              │   ──────────────────      │  │   ─────────────────      │
              │   • Logo & Branding       │  │   Props:                 │
              │   • System Status         │  │   • symbol, symbols      │
              │                           │  │   • mode                 │
              │   Sub-components:         │  │   • callbacks            │
              │   └─ StatusIndicator      │  │                          │
              │      (online/offline)     │  │   Sub-components:        │
              └───────────────────────────┘  │   ├─ ConnectionStatus   │
                                             │   ├─ SymbolSelector     │
                                             │   └─ TimeRangeSelector  │
                                             └──────────────────────────┘
                              │
                              ├──────────────────────────┐
                              │                          │
                              ▼                          ▼
              ┌───────────────────────────┐  ┌──────────────────────────┐
              │   ChartSection.tsx        │  │   DashboardFooter.tsx    │
              │   ─────────────────       │  │   ────────────────────   │
              │   Props:                  │  │   Props:                 │
              │   • symbol                │  │   • currentTime          │
              │   • mode                  │  │                          │
              │   • indicators            │  │   • MongoDB status       │
              │                           │  │   • Last updated time    │
              │   Contains:               │  └──────────────────────────┘
              │   └─ ChartEmbedded        │
              │      (existing component) │
              └───────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────────────┐
              │   TechnicalIndicatorsModal.tsx        │
              │   (existing component)                │
              │   ─────────────────────────────       │
              │   Props:                              │
              │   • open, onClose                     │
              │   • indicators, onChange              │
              └───────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Shared Resources                            │
├─────────────────────────────────────────────────────────────────┤
│  types/trading.ts                                               │
│  ├─ TimeRangeMode, SymbolOption                                 │
│  ├─ TechnicalIndicatorsConfig, IndicatorConfig                  │
│  └─ OrderBookEntry, Trade (for future use)                      │
│                                                                 │
│  constants/theme.ts                                             │
│  ├─ COLORS (background, border, text, status, trading)          │
│  ├─ SHADOWS (sm, md)                                            │
│  └─ BORDER_RADIUS (sm, md, lg)                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Disabled Features (Future)                         │
├─────────────────────────────────────────────────────────────────┤
│  OrderBookTradesSection.disabled.tsx                            │
│  • Complete Order Book implementation                           │
│  • Market Trades display                                        │
│  • WebSocket management                                         │
│  • Ready for re-enablement when Redis/Kafka available           │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
──────────
1. TradingDashboard fetches symbols from API → stores in state
2. User selects symbol → ControlPanel calls onSymbolChange
3. TradingDashboard updates symbol state → ChartSection re-renders
4. User clicks time range → TimeRangeSelector calls onModeChange
5. TradingDashboard updates mode state → ChartSection re-renders
6. ChartEmbedded fetches data from MongoDB based on symbol + mode
7. Timer updates currentTime → DashboardFooter displays updated time

Component Sizes:
────────────────
Before: TradingDashboard.tsx = 700 lines (monolithic)
After:
  • TradingDashboard.tsx = ~120 lines (orchestrator)
  • DashboardHeader.tsx = 82 lines
  • ControlPanel.tsx = 167 lines
  • ChartSection.tsx = 89 lines
  • DashboardFooter.tsx = 29 lines
  • trading.ts = 65 lines
  • theme.ts = 36 lines
  ────────────────────────────────
  Total: ~588 lines (organized + reusable)
  Saved from comments: ~300 lines moved to separate file
```
