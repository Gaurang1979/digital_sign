#ifndef _AES_H_
#define _AES_H_

#include "../../include/cryptoki_ext.h"

extern CK_SESSION_HANDLE hSession;
extern CK_FUNCTION_LIST_PTR m_gToken;

class AESTest 
{
public:
	AESTest(void);
	virtual ~AESTest();
	void Test(void);
private:
	void GenerateKey(void);
	void crypt_Single(void);
	void crypt_Update(void);
	
private:
	CK_OBJECT_HANDLE m_hKey;

};
#endif
