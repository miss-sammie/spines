// review-queue.js - extracted from Spines v1 review queue page
// Provides client-side behaviour for the admin review queue in Spines 2.0.
// NOTE: endpoints are already aligned with v2 backend.

/* eslint-disable */
// Wrap in IIFE to avoid leaking globals
(() => {
    let reviewQueue = [];

    // Navigation function for cache busting
    function navigateBackToLibrary(event) {
        event?.preventDefault();
        const timestamp = Date.now();
        window.location.href = `/?t=${timestamp}`;
    }

    async function loadReviewQueue() {
        try {
            const res = await fetch('/api/review-queue');
            if (!res.ok) throw new Error('Failed to load review queue');
            const data = await res.json();
            reviewQueue = data.queue || [];
            displaySummary(data.summary || {});
            displayReviewItems(reviewQueue);
        } catch (err) {
            showFeedback(err.message, 'error');
        }
    }

    function displaySummary(summary) {
        const grid = document.getElementById('summaryGrid');
        if (!grid) return;
        grid.innerHTML = `
            <div class="stat-card"><div class="stat-number">${summary.total || 0}</div><div class="stat-label">total</div></div>
            <div class="stat-card"><div class="stat-number">${summary.pending_review || 0}</div><div class="stat-label">pending</div></div>
            <div class="stat-card"><div class="stat-number">${summary.file_missing || 0}</div><div class="stat-label">missing</div></div>
            <div class="stat-card"><div class="stat-number">${summary.processing_failed || 0}</div><div class="stat-label">failed</div></div>`;
    }

    function displayReviewItems(queue) {
        const container = document.getElementById('reviewItems');
        const empty = document.getElementById('emptyState');
        if (!container) return;

        const pending = queue.filter(q => q.status === 'pending_review');
        if (pending.length === 0) {
            container.style.display = 'none';
            if (empty) empty.style.display = 'block';
            return;
        }
        container.style.display = 'grid';
        if (empty) empty.style.display = 'none';

        // Render using BookCard review variant
        container.innerHTML = pending.map(item => {
            return BookCard.generate(item, { variant: 'review', enableEditing: false });
        }).join('');

        pending.forEach(it => updateReviewFields(it.id));
        setTimeout(populateContributorFields, 200);
    }

    window.updateReviewFields = function(itemId){
        const editor=document.getElementById(`editor-${itemId}`);
        if(!editor) return;const type=editor.querySelector('[data-field="media_type"]').value;
        editor.querySelectorAll('.url-field').forEach(el=>el.style.display='none');
        editor.querySelectorAll('.isbn-field').forEach(el=>el.style.display='');
        if(type==='web'){editor.querySelectorAll('.url-field').forEach(el=>el.style.display='');editor.querySelectorAll('.isbn-field').forEach(el=>el.style.display='none');}
    };

    function populateContributorFields(){const saved=localStorage.getItem('spines_contributor');if(!saved) return;document.querySelectorAll('.contributor-input').forEach(i=>{if(i.value==='anonymous') i.value=saved;});}

    window.previewPdf=function(id){const frame=document.getElementById(`preview-${id}`);if(!frame) return;frame.style.display=frame.style.display==='none'?'block':'none';if(frame.src==='') frame.src=`/api/review-queue/${id}/pdf`;};

    function collectMetadata(itemElement){const inputs=itemElement.querySelectorAll('.metadata-input');const meta={};inputs.forEach(input=>{const field=input.dataset.field;if(!field) return;const visible=input.offsetParent!==null;const always=['media_type','title','author','year','isbn','url','publisher','read_by','tags','notes'];if(always.includes(field)||visible){let val=input.value.trim();if(field==='year'&&val) val=parseInt(val)||null;if(['read_by','tags'].includes(field)){val=val?val.split(',').map(s=>s.trim()).filter(Boolean):[];}meta[field]=val||null;}});return meta;}

    async function handleApprove(id){const itemEl=document.getElementById(`item-${id}`);if(!itemEl) return;const meta=collectMetadata(itemEl);const contributor=itemEl.querySelector('.contributor-input').value.trim()||'anonymous';itemEl.classList.add('loading');try{let copyAction='auto';const res=await fetch(`/api/review-queue/${id}/similar-books`);if(res.ok){const data=await res.json();if(data.has_matches){copyAction=await showCopyOptionsDialog(data.similar_books,contributor);if(!copyAction){itemEl.classList.remove('loading');return;}}}
        const resp=await fetch(`/api/review-queue/${id}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({metadata:meta,contributor,copy_action:copyAction})});if(!resp.ok){const err=await resp.json();throw new Error(err.error||'approve failed');}showFeedback('✅ Book processed','success');
        itemEl.remove();
        setTimeout(() => {
            navigateBackToLibrary();
        }, 1200);
    }catch(e){showFeedback(e.message,'error');}finally{itemEl.classList.remove('loading');}}

    window.approveItem=handleApprove;

    window.rejectItem=async function(id){const itemEl=document.getElementById(`item-${id}`);if(!itemEl) return;const filename=itemEl.querySelector('.review-title')?.textContent||'this item';if(!confirm(`Reject "${filename}" and remove from queue?`)) return;itemEl.classList.add('loading');try{const res=await fetch(`/api/review-queue/${id}/reject`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'user_rejected'})});if(!res.ok){const err=await res.json();throw new Error(err.error||'reject failed');}showFeedback('🗑️ item rejected','success');itemEl.remove();setTimeout(loadReviewQueue,1000);}catch(e){showFeedback(e.message,'error');}finally{itemEl.classList.remove('loading');}};

    window.recheckIsbn=async function(id){const editor=document.getElementById(`editor-${id}`);const isbnInput=editor.querySelector('[data-field="isbn"]');const isbn=isbnInput.value.trim();if(!isbn){showFeedback('Enter an ISBN first','error');return;}const btn=editor.querySelector('button[onclick*="recheckIsbn"]');btn.disabled=true;btn.textContent='⏳';try{const res=await fetch('/api/library/isbn-lookup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({isbn})});const data=await res.json();if(!res.ok) throw new Error(data.error||'ISBN lookup failed');if(data.found){const titleInput=editor.querySelector('[data-field="title"]');const authorInput=editor.querySelector('[data-field="author"]');const yearInput=editor.querySelector('[data-field="year"]');const pubInput=editor.querySelector('[data-field="publisher"]');if(data.metadata.title) titleInput.value=data.metadata.title;if(data.metadata.author) authorInput.value=data.metadata.author;if(data.metadata.year) yearInput.value=data.metadata.year;if(data.metadata.publisher) pubInput.value=data.metadata.publisher;showFeedback('Metadata updated from ISBN','success');}else{showFeedback('No metadata found for ISBN','info');}}catch(e){showFeedback(e.message,'error');}finally{btn.disabled=false;btn.textContent='🔍';}};

    function showCopyOptionsDialog(similarBooks, contributor){return new Promise(resolve=>{const modal=document.createElement('div');modal.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000;';const dlg=document.createElement('div');dlg.style.cssText='background:white;border:2px solid black;padding:20px;max-width:600px;max-height:80vh;overflow-y:auto;font-family:inherit;';dlg.innerHTML=`<h3>Similar books found</h3><p style="font-size:12px;color:#666">Choose how to handle:</p><div style="border:1px solid #ccc;padding:10px;margin-bottom:15px;max-height:200px;overflow:auto;">${similarBooks.map(b=>`<div style="padding:5px 0;border-bottom:1px solid #eee"><strong>${b.title}</strong> by ${b.author} (${b.year||'?'})<br><small style="color:#666">contributors: ${b.contributors.join(', ')||'none'} • confidence ${(b.confidence*100).toFixed(0)}%</small></div>`).join('')}</div><label style="display:block;margin-bottom:8px;font-weight:bold;"><input type="radio" name="copyAction" value="separate_copy" checked> Create separate copy for "${contributor}"</label><label style="display:block;margin:8px 0;font-weight:bold;"><input type="radio" name="copyAction" value="add_to_existing"> Add contributor to existing</label><label style="display:block;margin:8px 0;font-weight:bold;"><input type="radio" name="copyAction" value="auto"> Auto decide</label><div style="margin-top:15px;text-align:right;"><button id="cancelBtn">Cancel</button> <button id="okBtn" style="background:#006600;color:white;border:2px solid #006600;">Proceed</button></div>`;modal.appendChild(dlg);document.body.appendChild(modal);dlg.querySelector('#cancelBtn').onclick=()=>{document.body.removeChild(modal);resolve(null);};dlg.querySelector('#okBtn').onclick=()=>{const act=dlg.querySelector('input[name="copyAction"]:checked').value;document.body.removeChild(modal);resolve(act);};modal.onclick=e=>{if(e.target===modal){document.body.removeChild(modal);resolve(null);}}});}

    function showFeedback(msg,type='info'){const fb=document.createElement('div');fb.className=`feedback ${type}`;fb.textContent=msg;document.body.appendChild(fb);setTimeout(()=>fb.remove(),4000);}

    // expose for inline HTML onclick
    window.updateReviewFields = window.updateReviewFields;
    window.previewPdf = window.previewPdf;
    
    // Make loadReviewQueue globally accessible for background processing
    window.loadReviewQueue = loadReviewQueue;

    // initialise
    document.addEventListener('DOMContentLoaded', loadReviewQueue);
})(); 