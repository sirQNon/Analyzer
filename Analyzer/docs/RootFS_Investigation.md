# rootfs Investigation

Date: 27 July 2026

## Objective

To determine what the /rootfs file inside root.img represents.

---

## FACTS

... (the entire FACTS section from the report)

---

## EVIDENCE

... (the entire EVIDENCE section)

---

## CONCLUSION

... (the entire CONCLUSION section)

---

## Result

Confirmed:

- root.img contains EXT4
- it contains a file named rootfs
- rootfs is SquashFS v4
- the current Analyzer can extract SquashFS as a file, but cannot read its contents
- the next stage of the project is to implement a SquashFS Reader

Translated with DeepL.com (free version)