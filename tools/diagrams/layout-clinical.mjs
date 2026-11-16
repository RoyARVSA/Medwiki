// Build-time only. Receive measured boxes, return orthogonal layout geometry.
// Text is never parsed as markup or executable diagram directives.
import { readFileSync } from 'node:fs';
import ELK from 'elkjs/lib/elk.bundled.js';

const graph = JSON.parse(readFileSync(0, 'utf8'));
const safeId = value => typeof value === 'string' && /^[a-z][a-z0-9-]*$/.test(value);
const dimension = value => Number.isFinite(value) && value > 0 && value <= 100000;
if (!safeId(graph.id) || !Array.isArray(graph.children) || !Array.isArray(graph.edges) ||
    graph.children.some(n => !safeId(n.id) || !dimension(n.width) || !dimension(n.height)) ||
    graph.edges.some(e => !safeId(e.id) || !Array.isArray(e.sources) || !Array.isArray(e.targets))) {
  throw new Error('Expected measured card geometry');
}
graph.layoutOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.edgeRouting': 'ORTHOGONAL',
  // ELK uses a time-derived seed for zero; a fixed nonzero value keeps rebuilds stable.
  'elk.randomSeed': '1',
  'elk.padding': '[top=24,left=24,bottom=24,right=24]',
  'elk.spacing.nodeNode': '48',
  'elk.spacing.edgeNode': '28',
  'elk.spacing.edgeEdge': '20',
  'elk.layered.spacing.nodeNodeBetweenLayers': '40',
  'elk.layered.spacing.edgeNodeBetweenLayers': '12',
  'elk.layered.spacing.edgeEdgeBetweenLayers': '20',
  'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
  'elk.layered.crossingMinimization.forceNodeModelOrder': 'true',
  'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
  'elk.layered.mergeEdges': 'false',
};
const layout = await new ELK().layout(graph);
process.stdout.write(JSON.stringify(layout));
