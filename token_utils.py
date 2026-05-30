from fastapi import  HTTPException, status,Depends
from jose import JWTError, jwt
from datetime import datetime, timedelta,UTC
from config import *
from fastapi.security import OAuth2PasswordBearer
# 1. 定义从请求头获取 token 的工具
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
# 创建 token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 验证 token（给需要登录的接口用）
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userID: str = payload.get("user_id")
        if userID is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 token"
            )
        return userID
    except JWTError:
        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={'code':401,'meg':"token 验证失败"}
        )
if __name__ == '__main__':
    a = create_access_token({'user_id':2})
    print( datetime.now(UTC) + timedelta(minutes=2))
    print(a)
    print(verify_token(a))

