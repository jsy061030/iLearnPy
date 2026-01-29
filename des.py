"""
Des Encryption of JLU CAS
Author: Jssys
Date: 1 19 2026
"""

def get_box_binary(i):
    """将整数转换为4位二进制字符串"""
    return bin(i)[2:].zfill(4)


def init_permute(original_data):
    """初始置换"""
    ip_byte = [0] * 64
    pairs = [(1, 0), (3, 2), (5, 4), (7, 6)]

    for i in range(4):
        for j in range(7, -1, -1):
            k = 7 - j
            ip_byte[i * 8 + k] = original_data[j * 8 + pairs[i][0]]
            ip_byte[i * 8 + k + 32] = original_data[j * 8 + pairs[i][1]]

    return ip_byte


def expand_permute(right_data):
    """扩展置换"""
    ep_byte = [0] * 48
    for i in range(8):
        ep_byte[i * 6 + 0] = right_data[31] if i == 0 else right_data[i * 4 - 1]
        ep_byte[i * 6 + 1] = right_data[i * 4]
        ep_byte[i * 6 + 2] = right_data[i * 4 + 1]
        ep_byte[i * 6 + 3] = right_data[i * 4 + 2]
        ep_byte[i * 6 + 4] = right_data[i * 4 + 3]
        ep_byte[i * 6 + 5] = right_data[0] if i == 7 else right_data[i * 4 + 4]

    return ep_byte


def xor(byte_one, byte_two):
    """异或运算"""
    result = [0] * len(byte_one)
    for i in range(len(byte_one)):
        result[i] = byte_one[i] ^ byte_two[i]
    return result


def sbox_permute(expand_byte):
    """S盒置换"""
    sbox_byte = [0] * 32

    sboxes = [
        [
            [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
            [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
            [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
            [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]
        ],
        [
            [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
            [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
            [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
            [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]
        ],
        [
            [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
            [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
            [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
            [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]
        ],
        [
            [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
            [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
            [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
            [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]
        ],
        [
            [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
            [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
            [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
            [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]
        ],
        [
            [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
            [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
            [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
            [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]
        ],
        [
            [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
            [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
            [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
            [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]
        ],
        [
            [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
            [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
            [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
            [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]
        ]
    ]

    for m in range(8):
        i = (expand_byte[m * 6] * 2) + expand_byte[m * 6 + 5]
        j = (expand_byte[m * 6 + 1] * 8) + (expand_byte[m * 6 + 2] * 4) + (expand_byte[m * 6 + 3] * 2) + expand_byte[m * 6 + 4]

        binary_str = get_box_binary(sboxes[m][i][j])
        sbox_byte[m * 4] = int(binary_str[0])
        sbox_byte[m * 4 + 1] = int(binary_str[1])
        sbox_byte[m * 4 + 2] = int(binary_str[2])
        sbox_byte[m * 4 + 3] = int(binary_str[3])

    return sbox_byte


def p_permute(sbox_byte):
    """P盒置换"""
    return [
        sbox_byte[15], sbox_byte[6], sbox_byte[19], sbox_byte[20], sbox_byte[28], sbox_byte[11], sbox_byte[27], sbox_byte[16],
        sbox_byte[0], sbox_byte[14], sbox_byte[22], sbox_byte[25], sbox_byte[4], sbox_byte[17], sbox_byte[30], sbox_byte[9],
        sbox_byte[1], sbox_byte[7], sbox_byte[23], sbox_byte[13], sbox_byte[31], sbox_byte[26], sbox_byte[2], sbox_byte[8],
        sbox_byte[18], sbox_byte[12], sbox_byte[29], sbox_byte[5], sbox_byte[21], sbox_byte[10], sbox_byte[3], sbox_byte[24]
    ]


def finally_permute(end_byte):
    """最终置换"""
    return [
        end_byte[39], end_byte[7], end_byte[47], end_byte[15], end_byte[55], end_byte[23], end_byte[63], end_byte[31],
        end_byte[38], end_byte[6], end_byte[46], end_byte[14], end_byte[54], end_byte[22], end_byte[62], end_byte[30],
        end_byte[37], end_byte[5], end_byte[45], end_byte[13], end_byte[53], end_byte[21], end_byte[61], end_byte[29],
        end_byte[36], end_byte[4], end_byte[44], end_byte[12], end_byte[52], end_byte[20], end_byte[60], end_byte[28],
        end_byte[35], end_byte[3], end_byte[43], end_byte[11], end_byte[51], end_byte[19], end_byte[59], end_byte[27],
        end_byte[34], end_byte[2], end_byte[42], end_byte[10], end_byte[50], end_byte[18], end_byte[58], end_byte[26],
        end_byte[33], end_byte[1], end_byte[41], end_byte[9], end_byte[49], end_byte[17], end_byte[57], end_byte[25],
        end_byte[32], end_byte[0], end_byte[40], end_byte[8], end_byte[48], end_byte[16], end_byte[56], end_byte[24]
    ]


def str_to_bt(string):
    """将字符串转换为64位二进制数组"""
    bt = [0] * 64

    if len(string) < 4:
        for i in range(len(string)):
            k = ord(string[i])
            for j in range(16):
                pow_val = 1 << (15 - j)
                bt[16 * i + j] = (k // pow_val) % 2
        for p in range(len(string), 4):
            for q in range(16):
                bt[16 * p + q] = 0
    else:
        for i in range(4):
            k = ord(string[i])
            for j in range(16):
                pow_val = 1 << (15 - j)
                bt[16 * i + j] = (k // pow_val) % 2

    return bt


def bt64_to_hex(byte_data):
    """将64位二进制数组转换为十六进制字符串"""
    hex_str = ""
    for i in range(16):
        binary_str = ""
        for j in range(4):
            binary_str += str(byte_data[i * 4 + j])
        value = int(binary_str, 2)
        hex_str += format(value, 'X')

    return hex_str


def get_key_bytes(key):
    """获取密钥字节数组"""
    iterator = len(key) // 4
    key_bytes = []

    for i in range(iterator):
        key_bytes.append(str_to_bt(key[i * 4:i * 4 + 4]))

    if len(key) % 4 > 0:
        key_bytes.append(str_to_bt(key[iterator * 4:]))

    return key_bytes


def generate_keys(key_byte):
    """生成子密钥"""
    key = [0] * 56
    keys = [[0] * 48 for _ in range(16)]

    loop = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]

    for i in range(7):
        for j in range(8):
            k = 7 - j
            key[i * 8 + j] = key_byte[8 * k + i]

    for i in range(16):
        for j in range(loop[i]):
            temp0 = key[0]
            temp28 = key[28]

            for k in range(27):
                key[k] = key[k + 1]
                key[28 + k] = key[29 + k]

            key[27] = temp0
            key[55] = temp28

        temp_key = [
            key[13], key[16], key[10], key[23], key[0], key[4], key[2], key[27],
            key[14], key[5], key[20], key[9], key[22], key[18], key[11], key[3],
            key[25], key[7], key[15], key[6], key[26], key[19], key[12], key[1],
            key[40], key[51], key[30], key[36], key[46], key[54], key[29], key[39],
            key[50], key[44], key[32], key[47], key[43], key[48], key[38], key[55],
            key[33], key[52], key[45], key[41], key[49], key[35], key[28], key[31]
        ]
        keys[i] = temp_key

    return keys


def enc(data_byte, key_byte):
    """DES加密"""
    keys = generate_keys(key_byte)
    ip_byte = init_permute(data_byte)
    ip_left = [0] * 32
    ip_right = [0] * 32
    temp_left = [0] * 32

    for k in range(32):
        ip_left[k] = ip_byte[k]
        ip_right[k] = ip_byte[32 + k]

    for i in range(16):
        for j in range(32):
            temp_left[j] = ip_left[j]
            ip_left[j] = ip_right[j]

        temp_right = xor(p_permute(sbox_permute(xor(expand_permute(ip_right), keys[i]))), temp_left)

        for n in range(32):
            ip_right[n] = temp_right[n]

    final_data = [0] * 64
    for i in range(32):
        final_data[i] = ip_right[i]
        final_data[32 + i] = ip_left[i]

    return finally_permute(final_data)


def encrypt_with_keys(bt, first_key_bt, second_key_bt, third_key_bt, first_length, second_length, third_length):
    """使用多个密钥进行加密"""
    temp_bt = bt[:]

    if first_key_bt is not None:
        for x in range(first_length):
            if first_key_bt[x] is not None:
                temp_bt = enc(temp_bt, first_key_bt[x])

    if second_key_bt is not None:
        for y in range(second_length):
            if second_key_bt[y] is not None:
                temp_bt = enc(temp_bt, second_key_bt[y])

    if third_key_bt is not None:
        for z in range(third_length):
            if third_key_bt[z] is not None:
                temp_bt = enc(temp_bt, third_key_bt[z])

    return temp_bt


def strEnc(data, first_key=None, second_key=None, third_key=None):
    """字符串加密"""
    enc_data = ""
    first_key_bt = None
    second_key_bt = None
    third_key_bt = None
    first_length = 0
    second_length = 0
    third_length = 0

    if first_key is not None and first_key != "":
        first_key_bt = get_key_bytes(first_key)
        first_length = len(first_key_bt)

    if second_key is not None and second_key != "":
        second_key_bt = get_key_bytes(second_key)
        second_length = len(second_key_bt)

    if third_key is not None and third_key != "":
        third_key_bt = get_key_bytes(third_key)
        third_length = len(third_key_bt)

    if data is not None and data != "":
        if len(data) < 4:
            bt = str_to_bt(data)
            enc_byte = encrypt_with_keys(bt, first_key_bt, second_key_bt, third_key_bt, first_length, second_length, third_length)
            enc_data += bt64_to_hex(enc_byte)
        else:
            iterator = len(data) // 4
            remainder = len(data) % 4

            for i in range(iterator):
                temp_data = data[i * 4:i * 4 + 4]
                temp_byte = str_to_bt(temp_data)
                enc_byte = encrypt_with_keys(temp_byte, first_key_bt, second_key_bt, third_key_bt, first_length, second_length, third_length)
                enc_data += bt64_to_hex(enc_byte)

            if remainder > 0:
                remainder_data = data[iterator * 4:]
                temp_byte = str_to_bt(remainder_data)
                enc_byte = encrypt_with_keys(temp_byte, first_key_bt, second_key_bt, third_key_bt, first_length, second_length, third_length)
                enc_data += bt64_to_hex(enc_byte)

    return enc_data


def desInit(username, passwd, lt):
    """Initialize DES encryption with username, password, and lt"""
    data = username + passwd + lt
    first_key = "1"
    second_key = "2"
    third_key = "3"

    encrypted = strEnc(data, first_key, second_key, third_key)
    return encrypted


if __name__ == "__main__":
    result = desInit("jiangsy2424", "Jsy6q061030", "LT-8839974-kOZLZPlGXKs95tmRamADw0nj6fKOzR-tpass")
    print(f"Encrypted: {result}")

    # 可选：解密（需要实现dec函数）
    # decrypted = strDec(result, "1", "2", "3")
    # print(f"Decrypted: {decrypted}")