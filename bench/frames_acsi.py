import socket, subprocess, sys, time, os, re
# frames.py <hd dir> <auto prg> [warm]: idle iterations per VBL AND VBLs per frame (frame counter @ $300008)
hd, prg = sys.argv[1], sys.argv[2]
sock='/tmp/claude-0/hatari.sock'
if os.path.exists(sock): os.remove(sock)
srv=socket.socket(socket.AF_UNIX); srv.bind(sock); srv.listen(1)
cmd=['xvfb-run','-a','-s','-screen 0 800x600x24','hatari','--configfile','/home/claude/work/hatari.cfg','--machine','ste','--memsize','4096','--tos','/home/claude/work/tos162.img','--fast-boot','true','--sound','off','--frameskips','0','--statusbar','false','--borders','false','--harddrive',hd,'--gemdos-drive','P','--acsi','0=/home/claude/work/acsi/disk.img','--disk-a','/home/claude/work/acsi/boot.st','--auto',prg,'--control-socket',sock,'--monitor','rgb']+(['--fast-forward','true'] if os.environ.get('FF') else [])
p=subprocess.Popen(cmd,stdout=open('/tmp/claude-0/fr.out','w'),stderr=subprocess.STDOUT)
srv.settimeout(20); conn,_=srv.accept()
def send(c): conn.sendall((c+'\n').encode())
time.sleep(float(sys.argv[3]) if len(sys.argv)>3 else 30)
send('hatari-debug memdump 0x3F0000 80'); time.sleep(float(os.environ.get('MEAS','8')))
send('hatari-debug memdump 0x3F0000 80'); time.sleep(1)
send('hatari-shortcut quit'); time.sleep(1); p.terminate()
out=open('/tmp/claude-0/fr.out').read()
lines=re.findall(r'^\s*\$?0*(3[fF][0-9a-fA-F]{4}):\s*((?:[0-9a-fA-F]{2}\s*)+)',out,re.M)
dumps=[];cur=None
for a,d in lines:
    if a.lower()=='3f0000':
        cur=''; dumps.append(cur)
    if cur is None: continue
    dumps[-1]+=''.join(d.split())
    cur=dumps[-1]
v=[];ex=[]
for d in dumps[:2]:
    b=bytes.fromhex(d)
    v.append((int.from_bytes(b[:4],'big'),int.from_bytes(b[4:6],'big'),int.from_bytes(b[8:12],'big')))
    ex.append([int.from_bytes(b[o:o+4],'big') for o in range(12,68,4)])
print(v)
if ex: print('underruns,loops,reads,ring,wr,maxread(ticks),minbuf,ringsize,freeram,musicok,x,chunk,cidx,rawstate,rawfail =',ex[-1])
if len(v)==2:
    di=v[1][0]-v[0][0]; dv=abs((v[1][1]-v[0][1]+32768)%65536-32768); df=v[1][2]-v[0][2]
    print('VBLs %d frames %d => %.2f VBL per frame (%.1f fps); idle iterations per VBL %.1f'%(dv,df,dv/max(df,1),50.05*df/max(dv,1),di/max(dv,1)))
