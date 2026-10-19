14043c000: sub rsp, 0x38
14043c004: call qword ptr [rip - 0x13ae7a]
14043c00a: mov qword ptr [rsp + 0x20], rax
14043c00f: test rax, rax
14043c012: je 0x14043c094
14043c018: lea rcx, [rip + 0x421]
14043c01f: call qword ptr [rip - 0x13cddd]
14043c025: test rax, rax
14043c028: je 0x14043c094
14043c02e: mov rcx, rax
14043c031: lea rdx, [rip + 0x488]
14043c038: call qword ptr [rip - 0x13cdee]
14043c03e: test rax, rax
14043c041: je 0x14043c094
14043c047: mov rcx, qword ptr [rsp + 0x20]
14043c04c: call rax
14043c04e: test rax, rax
14043c051: je 0x14043c094
14043c057: mov qword ptr [rsp + 0x28], rax
14043c05c: lea rcx, [rip + 0x41d]
14043c063: call qword ptr [rip - 0x13ce21]
14043c069: test rax, rax
14043c06c: je 0x14043c094
14043c072: mov rcx, rax
14043c075: lea rdx, [rip + 0x4c4]
14043c07c: call qword ptr [rip - 0x13ce32]
14043c082: test rax, rax
14043c085: je 0x14043c094
14043c08b: mov rcx, qword ptr [rsp + 0x28]
14043c090: xor edx, edx
14043c092: call rax
14043c094: mov rax, qword ptr [rsp + 0x20]
14043c099: add rsp, 0x38
14043c09d: ret 