#include "AESTest.h"
#include "Common.h"

#define _CHECK_RV(info,rv) {if(rv){printf("Error:%x,%s\n",rv,info);return;} else {printf("%s:ok\n",info);}}

AESTest::AESTest()
{
	m_hKey = 0;
}

AESTest::~AESTest()
{

}


void AESTest::Test()
{
	GenerateKey();
	if(m_hKey == 0)
	{
		return ;
	}
	crypt_Single();
	crypt_Update();
}
void AESTest::GenerateKey()
{
	CK_OBJECT_CLASS oClass = CKO_SECRET_KEY;
	CK_KEY_TYPE keyType = CKK_AES; 
	CK_BBOOL bTrue = true;
	CK_BBOOL bFalse = false;
	CK_ULONG ulLen = 16;
	CK_MECHANISM mechanism = {CKM_AES_KEY_GEN, NULL_PTR, 0};
	CK_ATTRIBUTE Aestem[] = {
		{CKA_CLASS, &oClass, sizeof(CK_OBJECT_CLASS)},
		{CKA_KEY_TYPE, &keyType, sizeof(CK_KEY_TYPE)},
		{CKA_TOKEN, &bFalse, sizeof(CK_BBOOL)},
		{CKA_PRIVATE, &bTrue, sizeof(CK_BBOOL)},
		{CKA_ENCRYPT, &bTrue, sizeof(CK_BBOOL)},
		{CKA_DECRYPT, &bTrue, sizeof(CK_BBOOL)},
		{CKA_VALUE_LEN, &ulLen, sizeof(CK_ULONG)}, 
	};
	CK_ULONG ulCount = 7;
	CK_RV rv = m_gToken->C_GenerateKey(hSession, &mechanism, Aestem, ulCount, &m_hKey); 
	_CHECK_RV("Generate AES key", rv);
}

void AESTest::crypt_Single()
{
	const CK_ULONG DATA_LENGTH = 1024*3;
	CK_BYTE bIn[DATA_LENGTH] = {0}, bTemp[DATA_LENGTH] = {0}, bOut[DATA_LENGTH] = {0};
	CK_ULONG ulIn = 0, ulOut = 0, ulTemp = 0;
	CK_ULONG Mechanism[3] = {CKM_AES_CBC, CKM_AES_ECB, CKM_AES_CBC_PAD};
	CK_BYTE_PTR bHint[3] = {(CK_BYTE_PTR)"CKM_AES_CBC: ",\
							(CK_BYTE_PTR)"CKM_AES_ECB: ",
							(CK_BYTE_PTR)"CKM_AES_CBC_PAD: "};

	for(int i=0;i<3;i++)
	{
		ulIn = 1024;
		if(i==2)
			ulIn = 1000;
		for(register CK_ULONG i0 = 0;i0<ulIn;i0++)
			bIn[i0] = (CK_BYTE)i0;
		
		
		printf("\nAES: C_Encrypt()/C_Decrypt(): %s\n", bHint[i]);

		//ecnrypt init:
		CK_BYTE iv[16] = {'*','2','1','0','4','z','y','b','*','2','1','0','4','z','y','b'};
		CK_MECHANISM ckMechanism = {Mechanism[i], iv, 16};

		CK_RV rv =  m_gToken->C_EncryptInit(hSession, &ckMechanism, m_hKey); 
		_CHECK_RV("C_EncryptInit()", rv);

		rv =  m_gToken->C_Encrypt(hSession, bIn, ulIn, NULL, &ulTemp);
		if(CKR_OK == rv)
			rv = m_gToken->C_Encrypt(hSession, bIn, ulIn, bTemp, &ulTemp);
		_CHECK_RV("C_Encrypt()", rv);

		ShowData(bIn, ulIn);
		ShowData(bTemp, ulTemp);

		rv = m_gToken->C_DecryptInit(hSession, &ckMechanism, m_hKey);
		_CHECK_RV("C_DecryptInit()", rv);

		rv = m_gToken->C_Decrypt(hSession, bTemp, ulTemp, NULL, &ulOut);
		if(CKR_OK == rv)
			rv = m_gToken->C_Decrypt(hSession, bTemp, ulTemp, bOut, &ulOut);
		_CHECK_RV("C_Decrypt()", rv);

		ShowData(bOut, ulOut);
		
		if(0 == memcmp(bIn, bOut, ulOut))
			printf("Check data ok\n");
		else
			printf("Check data error\n");
	}
}

void AESTest::crypt_Update()
{
	const CK_ULONG DATA_LENGTH = 1024*3;
	CK_BYTE bIn[DATA_LENGTH] = {0}, bTemp[DATA_LENGTH] = {0}, bOut[DATA_LENGTH] = {0};
	CK_ULONG ulIn = 0, ulOut = 0, ulTemp = 0;
	CK_ULONG Mechanism[3] = {CKM_AES_CBC, CKM_AES_ECB, CKM_AES_CBC_PAD};
	CK_BYTE_PTR bHint[3] = {(CK_BYTE_PTR)"CKM_AES_CBC: ",\
							(CK_BYTE_PTR)"CKM_AES_ECB: ",\
							(CK_BYTE_PTR)"CKM_AES_CBC_PAD: "};

	for(int i=0;i<3;i++)
	{
		ulIn = 1024;
		if(i == 2)
		{
			ulIn = 1000;
		}
		for(register CK_ULONG i0 = 0;i0<ulIn;i0++)
			bIn[i0] = (CK_BYTE)i0;

		printf("\nAES: C_EncryptUpdate()/C_DecryptUpdate(): %s\n", bHint[i]);

		//ecnrypt init:
		CK_BYTE iv[16] = {'*','2','1','0','4','z','y','b','*','2','1','0','4','z','y','b'};
		CK_MECHANISM ckMechanism = {Mechanism[i], iv, sizeof(iv)};

		CK_RV rv =  m_gToken->C_EncryptInit(hSession, &ckMechanism, m_hKey); 
		_CHECK_RV("C_EncryptInit()", rv);
		
		CK_ULONG ulEncrypted = 0;

		//invoked twice:
		const CK_ULONG ulEnc1stPice = 33;
		rv = m_gToken->C_EncryptUpdate(hSession, bIn, ulEnc1stPice, NULL, &ulTemp);//get buffer's size.
		if(CKR_OK == rv)
			rv = m_gToken->C_EncryptUpdate(hSession, bIn, ulEnc1stPice, bTemp, &ulTemp);
		_CHECK_RV("C_EncryptUpdate(1)", rv);
		
		ulEncrypted+=ulTemp;
		ulTemp = 0;

		rv = m_gToken->C_EncryptUpdate(hSession,  &(bIn[ulEnc1stPice]), ulIn-ulEnc1stPice, NULL, &ulTemp);//get buffer's size.
		if(CKR_OK == rv)
			rv = m_gToken->C_EncryptUpdate(hSession, &(bIn[ulEnc1stPice]), ulIn-ulEnc1stPice, &(bTemp[ulEncrypted]), &ulTemp);
		_CHECK_RV("C_EncryptUpdate(2)", rv);

		ulEncrypted+=ulTemp;
		ulTemp = 0;

		rv = m_gToken->C_EncryptFinal(hSession, NULL, &ulTemp);//Get buffer's size:
		if(CKR_OK == rv)
			rv = m_gToken->C_EncryptFinal(hSession, &(bTemp[ulEncrypted]), &ulTemp);

		_CHECK_RV("C_EncryptFinal()", rv);

		ulEncrypted+=ulTemp;
		ulTemp = 0;

		ShowData(bIn, ulIn);
		ShowData(bTemp, ulEncrypted);
		 
		rv =  m_gToken->C_DecryptInit(hSession, &ckMechanism, m_hKey);
		_CHECK_RV("C_DecryptInit()", rv);
		
		CK_ULONG ulDecrypt = 0;
		const CK_ULONG ulDec1stPice = 17;

		rv = m_gToken->C_DecryptUpdate(hSession, bTemp, ulDec1stPice, NULL, &ulOut);//Get buffer's size
		if(CKR_OK == rv)
			rv = m_gToken->C_DecryptUpdate(hSession, bTemp, ulDec1stPice, bOut, &ulOut);
		_CHECK_RV("C_DecryptUpdate(1)", rv);

		ulDecrypt +=ulOut;
		ulOut = 0;

		//Get decrypted data:
		rv = m_gToken->C_DecryptUpdate(hSession, &(bTemp[ulDec1stPice]), ulEncrypted-ulDec1stPice, NULL, &ulOut);//Get buffer's size
		if(CKR_OK == rv)
			rv = m_gToken->C_DecryptUpdate(hSession, &(bTemp[ulDec1stPice]), ulEncrypted-ulDec1stPice, &(bOut[ulDecrypt]), &ulOut);
		_CHECK_RV("C_DecryptUpdate(2)", rv);

		ulDecrypt +=ulOut;
		ulOut = 0;

		rv = m_gToken->C_DecryptFinal(hSession, NULL, &ulOut);//Get buffer's size
		if(CKR_OK == rv)
			rv = m_gToken->C_DecryptFinal(hSession, &(bOut[ulDecrypt]), &ulOut);
		_CHECK_RV("C_DecryptFinal()", rv);

		ulDecrypt +=ulOut;
		
		ShowData(bOut, ulDecrypt);
		
		if(0 == memcmp(bIn, bOut, ulDecrypt))
			printf("Check data ok");
		else
			printf("Check data error\n");
	}
	m_gToken->C_DestroyObject(hSession, m_hKey);
}
