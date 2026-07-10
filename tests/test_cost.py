import time

from ultra_sandbox.cost import MacHostClock


def test_24h_blocks(isolated_config):
    clk = MacHostClock(isolated_config)
    assert clk.summary()["allocated"] is False

    clk.mark_allocated(when=time.time() - 3600 * 30)  # 30h ago
    s = clk.summary()
    assert s["billing_blocks"] == 2 and s["billed_hours"] == 48
    assert 17.5 < s["remaining_in_block_hours"] <= 18.5

    clk.mark_released()
    assert clk.summary()["allocated"] is False
