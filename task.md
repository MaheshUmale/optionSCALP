# OptionScalp - Active Tasks (Updated: 2026-01-23)

## ✅ Completed Work

### System Stabilization & Core Fixes
- [x] Fixed TvDatafeed crash (Chrome cookie decryption error)
- [x] Restored Upstox connection with proper error handling
- [x] Fixed WebSocket Runtime Error
- [x] Handle WebSocketDisconnect gracefully
- [x] Fixed Division by Zero in Master Strategies
- [x] Fixed PnL Widget DOM Mismatch

### UI & Chart Improvements
- [x] Fix Chart Rendering (Black Screen) - Upgraded Lightweight Charts to v4.1.1
- [x] Fix Chart Y-Axis Scaling - Added zero-value filtering and auto-fit
- [x] Fix Chart Sync Error (setCrosshairPosition) 
- [x] Implement "Command Center" Layout
- [x] Integrate Replay Mode into Main Dashboard
- [x] Fix Popout Chart Signals
- [x] Synchronize Charts (Zoom & Time)

### Replay Mode & Data Flow
- [x] Fix Replay Mode (LOAD/PLAY for BANKNIFTY)
- [x] Fix Empty Strategies and Positions Panels
- [x] Fix PCR Data and Status Sync
- [x] Optimize Database (WAL mode enabled)

## 🔧 In Progress

### Current Issue: NIFTY Replay Not Working
- **Status**: BANKNIFTY replay works perfectly, NIFTY replay loads data but doesn't progress (stuck at 0/994)
- **Investigation**: 
  - Added debug logging to trace data flow
  - Confirmed data is loaded (828 bars for index)
  - Issue appears to be in `send_replay_step` or data alignment between Index/Options
- **Next Steps**:
  - Identify why replay loop doesn't increment for NIFTY
  - Check time alignment between NIFTY spot and option data
  - Verify symbol resolution for NIFTY options

## 📋 Pending Tasks

### Performance & Optimization
- [ ] Implement Trendlyne Data Caching
- [ ] Optimize replay data loading for large datasets
- [ ] Add loading states for better UX

### Known Issues to Address
- [ ] Fix NIFTY Replay progression
- [ ] Chart header still shows "BANKNIFTY" when NIFTY is selected
- [ ] Verify chart display edge cases

## 📊 System Status

**Server**: ✅ Running (stable with patched TvFeed)
**Upstox Connection**: ⚠️ Thread shutdown warnings on exit (non-critical)
**Charts**: ✅ Rendering correctly with proper scaling
**Replay (BANKNIFTY)**: ✅ Fully functional
**Replay (NIFTY)**: ❌ Loads but doesn't progress

## 🎯 Priority for Next Session

1. **HIGH**: Fix NIFTY replay data progression issue
2. **MEDIUM**: Update chart header to reflect selected index
3. **LOW**: Implement data caching for performance
