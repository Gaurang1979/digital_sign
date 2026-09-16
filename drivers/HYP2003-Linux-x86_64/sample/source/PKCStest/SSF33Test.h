
#ifndef SSF33TEST_H 
#define  SSF33TEST_H 

#include "../../include/cryptoki_ext.h"

extern CK_SESSION_HANDLE hSession;
extern CK_FUNCTION_LIST_PTR m_gToken;

class Ssf33Test
{
public:
	Ssf33Test(void);
	virtual ~Ssf33Test();
	void Test(void);
private:
	void GenerateKey(void);
	void crypt_Single(void);
	void crypt_Update(void);
	
private:
	CK_OBJECT_HANDLE m_hKey;
};

#endif
