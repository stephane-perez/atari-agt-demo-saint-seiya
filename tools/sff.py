import struct
def rle(data, w, h, bpl):
    out=bytearray(); i=0; n=bpl*h
    while len(out)<n and i<len(data):
        b=data[i]; i+=1
        if b>=0xC0:
            c=b&0x3F; out+=bytes([data[i]])*c; i+=1
        else: out.append(b)
    return out
def load(path):
    d=open(path,'rb').read()
    ng,ni,off,sh=struct.unpack('<IIII',d[16:32])[0:4] if False else struct.unpack('<IIII',d[16:32])
    subs=[]; prev_pal=None
    for n in range(ni):
        nxt,ln,x,y,g,idx,link,same=struct.unpack('<IIhhhhhB',d[off:off+19])
        body=d[off+32:off+32+ln] if ln else b''
        e=dict(n=n,group=g,index=idx,x=x,y=y,link=link,same=same)
        if ln:
            xmin,ymin,xmax,ymax=struct.unpack('<HHHH',body[4:12])
            w=xmax-xmin+1;h=ymax-ymin+1
            bpl=struct.unpack('<H',body[66:68])[0]
            pix=rle(body[128:],w,h,bpl)
            rows=[pix[r*bpl:r*bpl+w] for r in range(h)]
            pal=None
            if len(body)>897 and body[-769]==0x0C and not same: pal=body[-768:]
            if pal is None: pal=prev_pal
            else: prev_pal=pal
            e.update(w=w,h=h,rows=rows,pal=pal)
        subs.append(e)
        if nxt==0: break
        off=nxt
    for e in subs:
        if 'rows' not in e:
            s=subs[e['link']]; e.update(w=s['w'],h=s['h'],rows=s['rows'],pal=s['pal'])
    return subs
