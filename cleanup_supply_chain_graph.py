"""
Script to remove all supply chain references from graph.py
"""
import re

def cleanup_graph_file():
    """Remove all supply chain analysis from graph.py"""

    with open('research_swarm/agents/fundamentalist/graph.py', 'r') as f:
        lines = f.readlines()

    output_lines = []
    skip_until_next_def = False
    in_supply_chain_node = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip entire supply chain node functions
        if 'def extract_supply_chain_node(' in line or 'def extract_supply_chain_ttm_node(' in line:
            # Skip until next 'def ' at column 0
            skip_until_next_def = True
            i += 1
            continue

        if skip_until_next_def:
            if line.startswith('def ') or line.startswith('# ===='):
                skip_until_next_def = False
                output_lines.append(line)
            i += 1
            continue

        # Remove supply chain node from workflow
        if '"extract_supply_chain"' in line or "'extract_supply_chain'" in line:
            i += 1
            continue

        # Update imports - remove SupplyChainOutput
        if 'SupplyChainOutput' in line and 'from research_swarm.agents.fundamentalist.models import' in line:
            line = line.replace('SupplyChainOutput,', '').replace(', SupplyChainOutput', '').replace('SupplyChainOutput', '')
            # Clean up double commas
            line = re.sub(r',\s*,', ',', line)
            output_lines.append(line)
            i += 1
            continue

        # Remove supply_chain parameter from function calls
        if 'supply_chain,' in line or ', supply_chain' in line:
            i += 1
            continue

        # Remove supply chain variable assignments
        if 'supply_chain =' in line and 'SupplyChainOutput(' in line:
            i += 1
            continue

        # Remove supply_chain_data checks
        if 'supply_chain_data' in line and ('get(' in line or 'ValueError' in line):
            # Remove the supply_chain_data part from conditionals
            line = line.replace(' or not state.get("supply_chain_data")', '')
            line = line.replace('or not state.get("supply_chain_data") ', '')
            line = line.replace('supply_chain_data or ', '')
            line = line.replace(', supply_chain_data', '')
            if line.strip() and 'supply_chain' not in line:
                output_lines.append(line)
            i += 1
            continue

        # Remove supply_chain_data from state initialization
        if '"supply_chain_data": None' in line:
            i += 1
            continue

        # Remove SupplyChainOutput imports in output building
        if 'SupplyChainOutput' in line and not 'from' in line:
            i += 1
            continue

        # Remove supply_chain_data from output building
        if 'supply_chain_data=' in line and 'SupplyChainOutput' in line:
            i += 1
            continue

        # Update edges - skip extract_supply_chain edges
        if 'extract_supply_chain' in line and 'add_edge' in line:
            i += 1
            continue

        # Update edge to skip supply chain node
        if 'add_edge("extract_metrics", "extract_supply_chain")' in line:
            output_lines.append(line.replace('"extract_supply_chain"', '"analyze_qualitative"'))
            i += 1
            continue

        if 'add_edge("extract_metrics_ttm", "extract_supply_chain_ttm")' in line:
            output_lines.append(line.replace('"extract_supply_chain_ttm"', '"analyze_qualitative_ttm"'))
            i += 1
            continue

        # Keep all other lines
        output_lines.append(line)
        i += 1

    # Write back
    with open('research_swarm/agents/fundamentalist/graph.py', 'w') as f:
        f.writelines(output_lines)

    print("✓ Cleaned up graph.py")
    print(f"  Removed supply chain nodes and references")

if __name__ == "__main__":
    cleanup_graph_file()
