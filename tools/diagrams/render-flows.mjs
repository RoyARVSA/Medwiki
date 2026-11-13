// Build-time only: accept the Python generator's JSON request on stdin.
// Never evaluate diagram directives, HTML, links, images or clinical rules here.
import { readFileSync } from 'node:fs';
import { render } from 'pele';

const request = JSON.parse(readFileSync(0, 'utf8'));
if (typeof request.source !== 'string' ||
    !/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(request.idPrefix ?? '') ||
    !request.source.startsWith('flowchart TD\n')) {
  throw new Error('Expected a generated flowchart and a safe unique ID prefix');
}
const { svg } = render(request.source, {
  fontSize: 18,
  idPrefix: request.idPrefix,
  links: false,
  images: false,
  fontFamily: 'sans-serif',
});
process.stdout.write(svg);
