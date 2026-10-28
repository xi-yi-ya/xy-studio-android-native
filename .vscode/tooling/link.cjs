// Keep editor-only dependencies separate from the application's package/lock files.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const link = path.join(root, 'node_modules');
const target = path.join(__dirname, 'node_modules');
if (!fs.existsSync(path.join(target, 'eslint/package.json'))) throw Error('Install .vscode/tooling dependencies first.');
if (!fs.existsSync(link)) fs.symlinkSync(target, link, 'junction');
else if (fs.realpathSync(link).toLowerCase() !== fs.realpathSync(target).toLowerCase()) throw Error('Existing root node_modules preserved; link not created.');
console.log('Editor tool dependencies available at ' + link);
