# Disassembler for the MB88400H/MB88500H microcontrollers
# 14.08.2026 by trwgQ26xxx
# Based on MAME MB88xx CPU dissasembler by Ernesto Corvi
# See: https://github.com/mamedev/mame/tree/master/src/devices/cpu/mb88xx

import sys
from pathlib import Path

def format_en_dis_comment(imm, is_enable):
	parts = []

	if imm & 0x01:
		parts.append(f"serial buffer full/empty interrupt {'enabled' if is_enable else 'disabled'}")
	if imm & 0x02:
		parts.append(f"timer/counter overflow interrupt {'enabled' if is_enable else 'disabled'}")
	if imm & 0x04:
		parts.append(f"external interrupt (IRQ) {'enabled' if is_enable else 'disabled'}")
	if imm & 0x08:
		parts.append(f"clock interrupt {'enabled' if is_enable else 'disabled'}")
	if imm & 0x10:
		parts.append(f"synchronous timing output (TO) {'started' if is_enable else 'stopped'}")
	if imm & 0x20:
		parts.append("prescaler clock reset" if is_enable else "prescaler clock no operation")
	if imm & 0x40:
		parts.append(f"serial port (SC) {'started' if is_enable else 'stopped'}")
	if imm & 0x80:
		parts.append(f"timer/counter (TC) {'started' if is_enable else 'stopped'}")

	if not parts:
		return "no EN/DIS-controlled function selected"

	return ", ".join(parts)


def disassemble(data):
	pc = 0
	lines = []
	vector_comments = {
		0x0000: ";RESET IRQ",
		0x0002: ";EXTERNAL IRQ",
		0x0004: ";TIMER IRQ",
		0x0006: ";SERIAL IRQ",
	}

	one_byte = {
		0x00: ("NOP",  "No operation"),
		0x01: ("OUTO", "If CF=0: O3-O0 <- AC, If CF=1: O7-O4 <- AC"),
		0x02: ("OUTP", "P <- AC"),
		0x03: ("OUT",  "(R)Y <- AC"),
		0x04: ("TAY",  "Y <- AC"),
		0x05: ("TATH", "TH <- AC"),
		0x06: ("TATL", "TL <- AC"),
		0x07: ("TAS",  "SB <- AC"),
		0x08: ("ICY",  "Y <- Y+1"),
		0x09: ("ICM",  "M(X,Y) <- M(X,Y)+1"),
		0x0A: ("STIC", "M(X,Y) <- AC, Y <- Y+1"),
		0x0B: ("X",    "AC <-> M(X,Y)"),
		0x0C: ("ROL",  "Rotate left through carry"),
		0x0D: ("L",    "AC <- M(X,Y)"),
		0x0E: ("ADC",  "AC <- AC + M(X,Y) + CF"),
		0x0F: ("AND",  "AC <- AC AND M(X,Y)"),
		0x10: ("DAA",  "Decimal Adjust Add"),
		0x11: ("DAS",  "Decimal Adjust Subtract"),
		0x12: ("INK",  "AC <- K"),
		0x13: ("IN",   "AC <- (R)Y"),
		0x14: ("TYA",  "AC <- Y"),
		0x15: ("TTHA", "AC <- TH"),
		0x16: ("TTLA", "AC <- TL"),
		0x17: ("TSA",  "AC <- SB (MB88401H/501H/503H) or AC <- SBL, X <- SBH (MB88505H 8-bit mode)"),
		0x18: ("DCY",  "Y <- Y-1"),
		0x19: ("DCM",  "M(X,Y) <- M(X,Y)-1"),
		0x1A: ("STDC", "M(X,Y) <- AC, Y <- Y-1"),
		0x1B: ("XX",   "AC <-> X"),
		0x1C: ("ROR",  "Rotate right through carry"),
		0x1D: ("ST",   "M(X,Y) <- AC"),
		0x1E: ("SBC",  "AC <- M(X,Y) - AC - CF"),
		0x1F: ("OR",   "AC <- AC OR M(X,Y)"),
		0x20: ("SETR", "Set register bit Y"),
		0x21: ("SETC", "CF <- 1"),
		0x22: ("RSTR", "Reset register bit Y"),
		0x23: ("RSTC", "CF <- 0"),
		0x24: ("TSTR", "Test register bit Y"),
		0x25: ("TSTI", "Test interrupt flag"),
		0x26: ("TSTV", "Test VF flag"),
		0x27: ("TSTS", "Test SF flag"),
		0x28: ("TSTC", "Test carry"),
		0x29: ("TSTZ", "Test ZF flag"),
		0x2A: ("STS",  "M(X,Y) <- SB"),
		0x2B: ("LS",   "SB <- M(X,Y)"),
		0x2C: ("RTS",  "Return from subroutine"),
		0x2D: ("NEG",  "Two's-complement negate AC"),
		0x2E: ("C",    "Compare M(X,Y) with AC"),
		0x2F: ("EOR",  "AC <- AC XOR M(X,Y)"),
		0x3C: ("RTI",  "Return from interrupt"),
		0x90: ("CLA",  "AC <- 0"),
	}

	while pc < len(data):
		start = pc
		op = data[pc]
		pc += 1

		if start in vector_comments:
			lines.append(vector_comments[start])

		# Default output
		inst = f"DB 0x{op:02X}"

		if op in one_byte:
			mnem, cmt = one_byte[op]
			inst = f"{mnem} ; {cmt}"

		elif 0x30 <= op <= 0x33:
			inst = f"SBIT {op & 3} ; Set memory bit {op & 3}"
		elif 0x34 <= op <= 0x37:
			inst = f"RBIT {op & 3} ; Reset memory bit {op & 3}"
		elif 0x38 <= op <= 0x3B:
			inst = f"TBIT {op & 3} ; Test memory bit {op & 3}"
		elif op == 0x3D:
			if pc >= len(data):
				inst = "EXT truncated"
			else:
				ext = data[pc]
				pc += 1

				if 0x00 <= ext <= 0x1F:
					inst = f"JPXY ${ext & 0x1F:02X} ; Unconditional page branch"
				elif 0x20 <= ext <= 0x3F:
					inst = f"LRXA #${ext & 0x1F:02X} ; X <- upper nibble of ROM(imm,X,Y), AC <- lower nibble"
				elif 0x80 <= ext <= 0x8F:
					imm = ext & 0x0F
					if imm == 0x1:
						inst = "ICA ; AC <- AC + 1"
					elif imm == 0xF:
						inst = "DCA ; AC <- AC - 1"
					else:
						inst = f"AI #${imm:X} ; AC <- AC + {imm}"
				elif 0x90 <= ext <= 0x9F:
					inst = f"LXID #${ext & 0xF:X} ; X <- {ext & 0xF}"
				elif 0xA0 <= ext <= 0xA3:
					inst = f"SBA {ext & 3} ; Set AC bit {ext & 3}"
				elif 0xA4 <= ext <= 0xA7:
					inst = f"RBA {ext & 3} ; Reset AC bit {ext & 3}"
				elif ext == 0xAC:
					inst = "ICX ; X <- X+1"
				elif ext == 0xAD:
					inst = "RST ; System initialization"
				elif ext == 0xAE:
					inst = "STBY ; Initiate standby mode (MB88500H only)"
				else:
					inst = f"EXT ILLEGAL ${ext:02X} ; undefined"
		elif op == 0x3E:
			imm = data[pc] if pc < len(data) else 0
			if pc < len(data):
				pc += 1
			inst = f"EN #${imm:02X} ; {format_en_dis_comment(imm, True)}"
		elif op == 0x3F:
			imm = data[pc] if pc < len(data) else 0
			if pc < len(data):
				pc += 1
			inst = f"DIS #${imm:02X} ; {format_en_dis_comment(imm, False)}"

		elif 0x40 <= op <= 0x43:
			inst = f"SETD {op & 3} ; Set port bit {op & 3}"
		elif 0x44 <= op <= 0x47:
			inst = f"RSTD {op & 3} ; Reset port bit {op & 3}"
		elif 0x48 <= op <= 0x4B:
			inst = f"TSTD {op & 3} ; Test port bit {op & 3}"
		elif 0x4C <= op <= 0x4F:
			inst = f"TBA {op & 3} ; Test AC bit {op & 3}"

		elif 0x50 <= op <= 0x53:
			inst = f"XD {op & 3} ; AC <-> M(0,{op & 3})"
		elif 0x54 <= op <= 0x57:
			inst = f"XYD {(op & 3)+4} ; Y <-> M(0,{(op & 3)+4})"

		elif 0x58 <= op <= 0x5F:
			inst = f"LXI #${op & 7:X} ; X3 <- 0, X[2:0] <- {op & 7}"

		elif 0x60 <= op <= 0x6F:
			lo = data[pc] if pc < len(data) else 0
			if pc < len(data):
				pc += 1
			inst = f"CALL ${((op & 0x0F) << 8) | lo:04X} ; Conditional subroutine call, if ST==1"

		elif 0x70 <= op <= 0x7F:
			lo = data[pc] if pc < len(data) else 0
			if pc < len(data):
				pc += 1
			inst = f"JPL ${((op & 0x0F) << 8) | lo:04X} ; Conditional long branch, if ST==1"

		elif 0x80 <= op <= 0x8F:
			inst = f"LYI #${op & 0xF:X} ; Y <- {op & 0xF}"

		elif 0x91 <= op <= 0x9F:
			inst = f"LI #${op & 0xF:X} ; AC <- {op & 0xF}"

		elif 0xA0 <= op <= 0xAF:
			inst = f"CYI #${op & 0xF:X} ; {op & 0xF} - Y"

		elif 0xB0 <= op <= 0xBF:
			inst = f"CI #${op & 0xF:X} ; {op & 0xF} - AC"

		elif 0xC0 <= op <= 0xFF:
			# Conditional branch targets stay within the current 64-byte page.
			target = (start & ~0x3F) | (op & 0x3F)
			inst = f"JMP ${target:04X} ; Conditional short branch, if ST==1"

		raw_bytes = " ".join(f"{b:02X}" for b in data[start:pc])
		lines.append(f"{start:04X}: {raw_bytes:<8} {inst}")

	return lines


def main():

	print("-------------------------------------------------------")
	print("Disassembler for the MB88400H/MB88500H microcontrollers")
	print("               14.08.2026 by trwgQ26xxx                ")
	print("-------------------------------------------------------")
	print("Based on MAME MB88xx CPU dissasembler  by Ernesto Corvi")
	print("-------------------------------------------------------")

	if len(sys.argv) < 2:
		print(f"Usage: {Path(sys.argv[0]).name} <input.bin> [output.asm]")
		sys.exit(1)

	input_path = Path(sys.argv[1])
	output_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else input_path.with_suffix(".asm")

	with input_path.open("rb") as f:
		data = f.read()

	listing = disassemble(data)

	with output_path.open("w", newline="\n") as f:
		for line in listing:
			f.write(line + "\n")

	print(f"Disassembled {len(data)} bytes.")
	print(f"Output written to {output_path}")

	print("Done.")

if __name__ == "__main__":
	main()
