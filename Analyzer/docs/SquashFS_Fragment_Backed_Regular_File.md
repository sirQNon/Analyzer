# Fragment-backed Basic Regular Files

Stage 13 integrates the existing basic regular-file reader with the Stage 12
fragment table.  Linux `squashfs_reg_inode` uses `fragment=0xffffffff` for no
fragment; otherwise `fragment` is a fragment-table index and `offset` is the
byte offset into its decoded fragment block.

For block size `B`, a valid fragment requires `tail_size = file_size % B` to be
nonzero.  The block list covers `floor(file_size / B)` complete blocks; a file
smaller than `B` can therefore consist entirely of its fragment tail.  The
reader appends exactly `fragment_block[offset:offset + tail_size]` after
checking both range bounds, then validates the final length against `file_size`.

`read_basic_regular_file()` keeps its existing signature and creates no second
fragment reader.  Fragment-table lookup and decompression remain in
`SquashFSFragmentTable`.  Invalid/missing fragment tails raise
`SquashFSFragmentTailError`; Stage 10's unsupported-fragment condition is no
longer used by the reader.

Extended regular inodes, fragment path resolution, and extraction integration
remain out of scope.
