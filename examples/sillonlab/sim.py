import sillonpy as sp
import numpy as np

sp.init("sillonlab")

top_param = np.linspace(1,10,100)

sp.log_param("top_param", top_param)
top_resut = top_param**2
sp.log_param("top_result", top_resut)
sp.add_note("Top Note")