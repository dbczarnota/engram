from index import ensure_vec_loadable


def test_vec_extension_loads():
    # Proves sqlite-vec's loadable extension works on this interpreter (spec §7).
    ensure_vec_loadable()
