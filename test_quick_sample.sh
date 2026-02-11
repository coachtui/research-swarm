#!/bin/bash
# Quick sample test - diverse scenarios

echo "🚀 Quick Robustness Sample Test"
echo "Testing 4 diverse scenarios..."
echo ""

# High momentum tech
python test_signal_robustness.py NVDA > /tmp/nvda.log 2>&1 &
PID1=$!

# Struggling blue chip  
python test_signal_robustness.py DIS > /tmp/dis.log 2>&1 &
PID2=$!

# Cyclical (energy)
python test_signal_robustness.py XOM > /tmp/xom.log 2>&1 &
PID3=$!

# Meme stock edge case
python test_signal_robustness.py GME > /tmp/gme.log 2>&1 &
PID4=$!

# Wait for all to complete
echo "Running tests in parallel..."
wait $PID1 $PID2 $PID3 $PID4

echo ""
echo "✅ All tests complete! Aggregating results..."
echo ""

# Extract key results
for ticker in NVDA DIS XOM GME; do
    echo "=== $ticker ==="
    grep "Overall" /tmp/$(echo $ticker | tr '[:upper:]' '[:lower:]').log | tail -1
    grep "Inst:" /tmp/$(echo $ticker | tr '[:upper:]' '[:lower:]').log | tail -1
    echo ""
done
