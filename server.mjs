import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

// Local static server. No AI key required, no server-side content injection.
// To publish a new edition, replace news.json; reload the browser.
const root=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PORT||4173);
const host=process.env.HOST||'127.0.0.1';
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8'};

const server=http.createServer(async(req,res)=>{
  if(req.method!=='GET'&&req.method!=='HEAD'){
    res.writeHead(405,{'Content-Type':'text/plain'});res.end('Method not allowed');return;
  }
  try{
    const requestPath=new URL(req.url,`http://${host}:${port}`).pathname;
    const decoded=decodeURIComponent(requestPath);
    const file=path.resolve(root,'.'+(decoded==='/'?'/index.html':decoded));
    if(!file.startsWith(root+path.sep)){
      res.writeHead(403);res.end('Forbidden');return;
    }
    const bytes=await fs.readFile(file);
    res.writeHead(200,{
      'Content-Type':mime[path.extname(file)]||'application/octet-stream',
      'Cache-Control':file.endsWith('news.json')?'no-store':'public, max-age=60',
      'X-Content-Type-Options':'nosniff',
    });
    res.end(req.method==='HEAD'?undefined:bytes);
  }catch(error){
    res.writeHead(error.code==='ENOENT'?404:500,{'Content-Type':'text/plain; charset=utf-8'});
    res.end(error.code==='ENOENT'?'Not found':'Server error');
  }
});
server.listen(port,host,()=>console.log(`THE SCROLL → http://${host}:${port}`));
