import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const children=[spawn(process.env.PYTHON||'python',['-m','uvicorn','services.api.main:app','--host','127.0.0.1','--port','8000'],{cwd:root,stdio:'inherit'}),
  spawn(process.execPath,['node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1'],{cwd:resolve(root,'apps/web'),stdio:'inherit'})];
let stopping=false;
function stop(){if(stopping)return;stopping=true;for(const child of children)child.kill();}
for(const child of children){child.on('error',e=>{console.error(e.message);stop();process.exitCode=1;});child.on('exit',code=>{if(!stopping){stop();process.exitCode=code||0;}});}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
