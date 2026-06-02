"""
Core interpolation functions for water level and volume calculations
"""

from thuyvan_data_client import interpolate_water_volume, query_nearby_water_levels


def interpolate_water_level_from_volume(target_volume, reservoir="Sông Hinh", hint_level=None):
    """
    Interpolate water level from volume (inverse interpolation)

    Args:
        target_volume: Target volume in million m³
        reservoir: Reservoir name
        hint_level: Optional water level (m) to query records near; if None, uses 200

    Returns:
        float: Water level in meters, or None if not found
    """
    try:
        # Query records near hint_level so we get volumes in the right range (e.g. 208m → ~280–300 triệu m³)
        center = hint_level if hint_level is not None else 200
        candidates = query_nearby_water_levels(center, limit=500, reservoir=reservoir)

        if not candidates:
            return None

        # Find closest volume match
        closest = min(candidates, key=lambda c: abs(c['Dungtich'] - target_volume))

        # If exact match or very close, return it
        if abs(closest['Dungtich'] - target_volume) < 0.001:
            return closest['Mucnuoc']

        # Find records below and above target volume
        below = [c for c in candidates if c['Dungtich'] <= target_volume]
        above = [c for c in candidates if c['Dungtich'] > target_volume]

        if not below or not above:
            # IMPROVED FALLBACK: Use linear estimation instead of closest point
            # For Sông Hinh: approximately 23 million m³ per meter
            if below:
                ref_record = max(below, key=lambda c: c['Dungtich'])
            elif above:
                ref_record = min(above, key=lambda c: c['Dungtich'])
            else:
                ref_record = closest

            # Calculate dynamic slope (dV/dH) from candidates if possible
            if len(candidates) >= 2:
                # Sort candidates by volume distance to target_volume to find nearest slope
                sorted_candidates = sorted(candidates, key=lambda c: abs(c['Dungtich'] - target_volume))
                c1 = sorted_candidates[0]
                c2 = sorted_candidates[1]
                dh = abs(c1['Mucnuoc'] - c2['Mucnuoc'])
                dv = abs(c1['Dungtich'] - c2['Dungtich'])
                slope = dv / dh if dh > 0 else (23.0 if "song hinh" in reservoir.lower() else 2.5)
            else:
                slope = 23.0 if "song hinh" in reservoir.lower() else 2.5

            volume_diff = target_volume - ref_record['Dungtich']
            estimated_h = ref_record['Mucnuoc'] + (volume_diff / slope)

            print(f"[ESTIMATE] V={target_volume:.3f} - Using linear estimation from V={ref_record['Dungtich']:.3f}(H={ref_record['Mucnuoc']:.2f}m) with slope={slope:.3f} → H≈{estimated_h:.2f}m", flush=True)
            return estimated_h

        # Get closest points
        V1_record = max(below, key=lambda c: c['Dungtich'])
        V2_record = min(above, key=lambda c: c['Dungtich'])

        H1 = V1_record['Mucnuoc']
        V1 = V1_record['Dungtich']
        H2 = V2_record['Mucnuoc']
        V2 = V2_record['Dungtich']

        print(f"[INTERPOLATE] V={target_volume:.3f} → Between V1={V1:.3f}(H={H1:.2f}m) and V2={V2:.3f}(H={H2:.2f}m)", flush=True)

        # Linear interpolation: H = H1 + (H2 - H1) * (V - V1) / (V2 - V1)
        if V2 == V1:
            return H1

        H = H1 + (H2 - H1) * (target_volume - V1) / (V2 - V1)
        print(f"[INTERPOLATE] Result: H={H:.2f}m", flush=True)
        return H

    except Exception as e:
        print(f"[ERROR] Cannot interpolate water level from volume: {e}", flush=True)
        return None
