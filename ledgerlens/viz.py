"""Visual helpers: evidence highlighting, the evidence graph image, ELA heatmap."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def highlight_full(page_image: str, bboxes, color=(220, 30, 40), width=4):
    """Return a PIL image of the full page with the given bboxes outlined."""
    img = Image.open(page_image).convert("RGB")
    d = ImageDraw.Draw(img)
    for b in bboxes:
        if not b:
            continue
        x, y, w, h = b
        d.rectangle([x - 3, y - 3, x + w + 3, y + h + 3], outline=color, width=width)
    return img


def highlight_crop(page_image: str, bbox, pad=55, color=(220, 30, 40), width=4,
                   out_path: str = None, max_w=520):
    """Return/save a cropped view around bbox with the region outlined."""
    img = Image.open(page_image).convert("RGB")
    W, H = img.size
    if bbox:
        x, y, w, h = bbox
        d = ImageDraw.Draw(img)
        d.rectangle([x - 3, y - 3, x + w + 3, y + h + 3], outline=color, width=width)
        cx0 = _clamp(x - pad, 0, W); cy0 = _clamp(y - pad, 0, H)
        cx1 = _clamp(x + w + pad, 0, W); cy1 = _clamp(y + h + pad, 0, H)
        crop = img.crop((cx0, cy0, cx1, cy1))
    else:
        crop = img
    if crop.width > max_w:
        ratio = max_w / crop.width
        crop = crop.resize((max_w, int(crop.height * ratio)))
    if out_path:
        crop.save(out_path)
        return out_path
    return crop


def render_evidence_graph(graph, out_path: str, documents=None):
    """Draw the evidence graph: entity nodes grouped, edges green (agree) / red (conflict)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    G = nx.Graph()
    for n in graph["nodes"]:
        G.add_node(n["id"], entity=n["entity"], doc=n["doc_id"], value=n["value"])
    for e in graph["edges"]:
        G.add_edge(e["a"], e["b"], agree=e["agree"])

    if len(G.nodes) == 0:
        return None
    pos = nx.spring_layout(G, seed=7, k=0.9)
    fig, ax = plt.subplots(figsize=(9, 6))
    agree_edges = [(u, v) for u, v, d in G.edges(data=True) if d["agree"]]
    conflict_edges = [(u, v) for u, v, d in G.edges(data=True) if not d["agree"]]
    nx.draw_networkx_edges(G, pos, edgelist=agree_edges, edge_color="#3f9b57", width=2, ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=conflict_edges, edge_color="#d81e28",
                           width=3, style="dashed", ax=ax)
    nx.draw_networkx_nodes(G, pos, node_color="#16365e", node_size=900, ax=ax)
    labels = {n: f"{G.nodes[n]['doc']}\n{G.nodes[n]['entity']}" for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=7, font_color="white", ax=ax)
    ax.set_title("Evidence graph (red dashed = cross-document conflict)", fontsize=11)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def ela_heatmap(image_path: str, out_path: str, quality=90):
    """Exploratory ELA heatmap (visual aid only, low confidence)."""
    import io
    import numpy as np
    from PIL import ImageChops
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    orig = Image.open(image_path).convert("RGB")
    buf = io.BytesIO(); orig.save(buf, format="JPEG", quality=quality); buf.seek(0)
    resaved = Image.open(buf).convert("RGB")
    diff = np.asarray(ImageChops.difference(orig, resaved)).astype("float32").sum(axis=2)
    fig, ax = plt.subplots(figsize=(5, 6))
    ax.imshow(diff, cmap="inferno")
    ax.set_title("ELA heatmap (exploratory, low confidence)", fontsize=10)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
